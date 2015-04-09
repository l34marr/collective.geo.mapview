#!/usrbin/env python

import json
import calendar
from datetime import datetime
from DateTime import DateTime

from Acquisition import aq_inner

from zope.interface import implements
from zope.component import getMultiAdapter, getUtility

from Products.Five.browser import BrowserView
from Products.CMFCore.utils import getToolByName
from Products.ATContentTypes.utils import DT2dt
from Products.AdvancedQuery import Eq, Ge, Le, In

from plone.uuid.interfaces import IUUID
from plone.memoize.instance import memoize
from plone.registry.interfaces import IRegistry

from .interfaces import IUshahidiMapView
from .map_settings_js import DEFAULT_MARKER_COLOR


class UshahidiMapView(BrowserView):

    implements(IUshahidiMapView)

    def friendly_types(self):
        pstate = getMultiAdapter((self.context, self.request),
            name=u'plone_portal_state')
        return pstate.friendly_types()

    @memoize
    def getObjectsInfo(self):
        context = aq_inner(self.context)
        catalog = getToolByName(context, 'portal_catalog')
        portal_types = getToolByName(context, 'portal_types')

        categories = set() # to store unique object keywords
        ctypes = [] # to store portal type and it's title
        ctypes_added = [] # to avoid duplicates in content types list
        ctypes_meta = {} # to cache portal type Titles

        query = Eq('path', '/'.join(context.getPhysicalPath())) & \
            In('portal_type', self.friendly_types()) & \
            Eq('object_provides',
                'collective.geo.geographer.interfaces.IGeoreferenceable')

        brains = catalog.evalAdvancedQuery(query, (('start', 'asc'),))
        for brain in brains:
            # skip if no coordinates set
            markers = self._get_markers(brain)
            if not markers:
                continue

            # populate categories
            if markers[0]['tags']:
                categories |= set(markers[0]['tags'])

            # populate types
            ptype = brain.portal_type
            if ptype not in ctypes_added:
                if ptype in ctypes_meta:
                    title = ctypes_meta[ptype]
                else:
                    title = portal_types.getTypeInfo(ptype).title
                    ctypes_meta[ptype] = title
                ctypes.append({'id': ptype, 'title': title})
                ctypes_added.append(ptype)

        # sort our data
        categories = list(categories)
        categories.sort()

        ctypes = list(ctypes)
        ctypes.sort(lambda x,y:cmp(x['title'], y['title']))

        # prepare dates, for this we just generate range of years and months
        # between first and last item fetched list of objects
        dates = []
        if len(brains) > 0:
            # skip object w/o set start date
            start_brain = None
            for brain in brains:
                # skip if no coordinates set
                markers = self._get_markers(brain)
                if not markers:
                    continue

                if brain.start and brain.start.year() > 1000:
                    start_brain = brain
                    break

            if start_brain:
                # now try to find last date, based on end field
                end_brain = None
                for brain in catalog.evalAdvancedQuery(query,
                    (('end', 'desc'),)):
                    # skip if no coordinates set
                    markers = self._get_markers(brain)
                    if not markers:
                        continue

                    if brain.end and brain.end.year() < 2499:
                        end_brain = brain
                        break

                if not end_brain:
                    end = brains[-1].start
                else:
                    end = end_brain.end

                start = start_brain.start
                first_year, last_year = start.year(), end.year()
                first_month, last_month = start.month(), end.month()

                if first_year and last_year:
                    for year in range(first_year, last_year+1):
                        months = []

                        # count from first month only for first year
                        month_from = 1
                        if year == first_year:
                            month_from = first_month

                        # count till last month only for last year
                        month_to = 12
                        if year == last_year:
                            month_to = last_month

                        month_name = {1: 'Jan', 2: 'Feb', 3: 'Mar',
                                      4: 'Apr', 5: 'May', 6: 'Jun',
                                      7: 'Jul', 8: 'Aug', 9: 'Sep',
                                     10: 'Oct', 11: 'Nov', 12: 'Dec'}
                        for month in range(month_from, month_to+1):
                            dt = datetime(year, month, 1)
                            months.append({
                                'datetime': dt,
                                'label': '%s %s' % (month_name[dt.month], year),
                                'timestamp': calendar.timegm(dt.timetuple()),
                            })

                        dates.append((year, months))

            # sort by year
            if dates:
                dates.sort(lambda x,y: cmp(x[0], y[0]))

        return {
            'categories': tuple(categories),
            'types': tuple(ctypes),
            'dates': tuple(dates),
        }

    def getDates(self):
        return self.getObjectsInfo()['dates']

    def getTypes(self):
        return self.getObjectsInfo()['types']

    def getCategories(self):
        """Returns list of keywords used in sub-objects of context"""
        result = []
        for cat in self.getObjectsInfo()['categories']:
            result.append({
                'label': cat,
                'color': '#' + self.getCategoryColor(cat),
            })
        return tuple(result)

    def getCategoryColor(self, category, default=DEFAULT_MARKER_COLOR):
        """Returns category color from registry"""
        registry = getUtility(IRegistry)
        colors = registry['collective.geo.mapview.keywords_colors']
        return colors.get(category, default)

    def _prepare_query(self):
        """Return query for catalog"""
        context = aq_inner(self.context)
        query = Eq('path', '/'.join(context.getPhysicalPath())) & \
            In('portal_type', self.friendly_types()) & \
            Eq('object_provides',
                'collective.geo.geographer.interfaces.IGeoreferenceable')

        # check if we need to apply category filter
        category = self.request.get('c') and [self.request.get('c')] or []
        if category:
            query &= In('Subject', category)

        # apply content types
        if self.request.get('m'):
            query &= Eq('portal_type', self.request['m'])

        # apply 'from' date
        start = self.request.get('s')
        if start and start != '0':
            query &= Ge('end', int(start))

        # apply 'to' date
        end = self.request.get('e')
        if end and end != '0':
            query &= Le('start', int(end))

        return query

    def _get_category_color(self):
        category = self.request.get('c') and [self.request.get('c')] or []
        color = DEFAULT_MARKER_COLOR
        if category:
            color = self.getCategoryColor(category[0],
                default=DEFAULT_MARKER_COLOR)
        return color

    def getJSONCluster(self):
        context = aq_inner(self.context)
        catalog = getToolByName(context, 'portal_catalog')
        purl = getToolByName(context, 'portal_url')()

        # get zoom and calculate distance based on zoom
        color = self._get_category_color()
        zoom = self.request.get('z') and int(self.request.get('z')) or 7
        distance = float(10000000 >> zoom) / 100000.0
        query = self._prepare_query()

        # query all markers for the map
        markers = []
        added = []
        for brain in catalog.evalAdvancedQuery(query, (
            ('start', 'asc'), ('end', 'desc'))):
            for m in self._get_markers(brain):
                if m['uid'] not in added:
                    markers.append(m)
                    added.append(m['uid'])

        # cluster markers based on zoom level
        clusters = []
        singles = []
        while len(markers) > 0:
            marker = markers.pop()
            cluster = []

            for target in markers[:]:
                pixels = abs(marker['longitude'] - target['longitude']) + \
                    abs(marker['latitude'] - target['latitude'])

                # if two markers are closer than defined distance, remove
                # compareMarker from array and add to cluster.
                if pixels < distance:
                    markers.pop(markers.index(target))
                    cluster.append(target)

            # if a marker was added to cluster, also add the marker we were
            # comparing to
            if len(cluster) > 0:
                cluster.append(marker)
                clusters.append(cluster)
            else:
                singles.append(marker)

        # create json from clusters
        features = []
        for cluster in clusters:
            # calculate cluster center
            bounds = self.calculate_center(cluster)

            # json string for popup window
            marker = cluster[0]

            start = marker['start']
            if start:
                start = calendar.timegm(DT2dt(start).timetuple())

            uids = '&'.join(['UID=%s' % m['search_uid'] for m in cluster])
            features.append({
                'type': 'Feature',
                'properties': {
                    'id': marker['uid'],
                    'name': '%d Items' % len(cluster),
                    'link': '%s/@@search?%s' % (purl, uids),
                    'category': marker['tags'],
                    'color': color,
                    'icon': '',
                    'thumb': '',
                    'timestamp': start,
                    'count': len(cluster),
                    'class': 'stdClass'
                },
                'geometry': {
                     'type': 'Point',
                     'coordinates': [bounds['center']['longitude'],
                         bounds['center']['latitude']]
                }
            })

        # pass single points to standard markers json
        for marker in singles:
            start = marker['start']
            if start:
                start = calendar.timegm(DT2dt(start).timetuple())

            features.append({
                'type': 'Feature',
                'properties': {
                    'id': marker['uid'],
                    'name': marker['title'],
                    'link': marker['url'],
                    'category': marker['tags'],
                    'color': color,
                    'icon': '',
                    'thumb': '',
                    'timestamp': start,
                    'count': 1,
                    'class': 'stdClass'
                },
                'geometry': marker['geometry'],
            })

        return json.dumps({"type":"FeatureCollection", "features": features})

    def calculate_center(self, cluster):
        """Calculates average lat and lon of clustered items"""
        south, west, north, east = 90, 180, -90, -180

        lat_sum = lon_sum = 0
        for marker in cluster:
            if marker['latitude'] < south:
                south = marker['latitude']

            if marker['longitude'] < west:
                west = marker['longitude']

            if marker['latitude'] > north:
                north = marker['latitude']

            if marker['longitude'] > east:
                east = marker['longitude']

            lat_sum += marker['latitude']
            lon_sum += marker['longitude']

        lat_avg = lat_sum / len(cluster)
        lon_avg = lon_sum / len(cluster)

        center = {'longitude': lon_avg, 'latitude': lat_avg}
        sw = {'longitude': west, 'latitude': south}
        ne = {'longitude': east, 'latitude': north}
        return {
            "center": center,
            "sw": sw,
            "ne": ne,
        }

    def getJSON(self):
        return json.dumps({})

    def getTimeline(self):
        data = []

        markers = []
        query = self._prepare_query()
        catalog = getToolByName(self.context, 'portal_catalog')
        for brain in catalog.evalAdvancedQuery(query, (
            ('start', 'asc'), ('end', 'desc'))):
            # skip if no coordinates set
            has_markers = self._get_markers(brain)
            if not has_markers:
                continue

            # skip if there is no valid start date set
            if not brain.start or brain.start.year() <= 1000:
                continue

            markers.append(brain)

        # prepare data from request
        interval = self.request.get('i', '') or 'month'
        from DateTime.interfaces import TimeError
        try:
            start = DateTime(int(self.request['s']))
        except TimeError:
            start = DateTime('1854/01/10 09:00:00 UTC')

        end = DateTime(int(self.request['e']))

        # 'month' interval
        if interval == 'month':
            months = {}
            for year, month, last_day in self._getMonthsRange(start, end):
                _from = DateTime(year, month, 1).earliestTime()
                _to = DateTime(year, month, last_day).latestTime()
                _date = calendar.timegm(datetime(year, month, 1).timetuple()
                    ) * 1000
                months.setdefault(_date, 0)
                for marker in markers:
                    if self._isObjWithinPeriod(marker, _from, _to):
                        months[_date] += 1

            # sort and filter out 'zero' months
            keys = months.keys()
            keys.sort()
            data = [[key, months[key]] for key in keys if months[key]]

        # 'week' interval
        if interval == 'week':
            weeks = {}
            for year, month, first_day, last_day in self._getWeeksRange(start,
                end):
                _from = DateTime(year, month, first_day).earliestTime()
                _to = DateTime(year, month, last_day).latestTime()
                _date = calendar.timegm(datetime(year, month,
                    first_day).timetuple()) * 1000
                weeks.setdefault(_date, 0)
                for marker in markers:
                    if self._isObjWithinPeriod(marker, _from, _to):
                        weeks[_date] += 1

            # sort and filter out 'zero' weeks
            keys = weeks.keys()
            keys.sort()
            data = [[key, weeks[key]] for key in keys if weeks[key]]

        # 'day' interval
        if interval == 'day':
            days = {}
            for year, month, day in self._getDaysRange(start, end):
                _from = DateTime(year, month, day).earliestTime()
                _to = DateTime(year, month, day).latestTime()
                _date = calendar.timegm(datetime(year, month, day).timetuple()
                    ) * 1000
                days.setdefault(_date, 0)
                for marker in markers:
                    if self._isObjWithinPeriod(marker, _from, _to):
                        days[_date] += 1

            # sort and filter out 'zero' days
            keys = days.keys()
            keys.sort()
            data = [[key, days[key]] for key in keys if days[key]]

        return json.dumps([{
            "label": self.request.get('c', '') or "All Categories",
            "color": self._get_category_color(),
            "data": data
        }])

    def _isObjWithinPeriod(self, brain, _from, _to):
        """Checks whether given object is lasting during passed month"""
        # no start set
        if not brain.start or brain.start.year() <= 1000:
            return False

        # is object after the end date?
        start = brain.start
        if start.greaterThan(_to):
            return False

        # if end date is set
        end = None
        if brain.end and brain.end.year() < 2499:
            end = brain.end
            # is object before the start date
            if end.lessThan(_from):
                return False

        return True

    def _getDaysRange(self, start, end):
        """Returns list of (year, month, day) tuples for passed
        start and end DateTimes.
        """
        my_cal = calendar.Calendar()
        first_year, last_year = start.year(), end.year()
        first_month, last_month = start.month(), end.month()

        days = []
        for year in range(first_year, last_year+1):
            # count from first month only for first year
            month_from = 1
            if year == first_year:
                month_from = first_month

            # count till last month only for last year
            month_to = 12
            if year == last_year:
                month_to = last_month

            for month in range(month_from, month_to+1):
                # loop over days in a month of the year
                days.extend([(year, month, day)
                    for day in my_cal.itermonthdays(year, month) if day])

        return days

    def _getWeeksRange(self, start, end):
        """Returns list of (year, month, first_day, last_day) tuples for passed
        start and end DateTimes.
        """
        my_cal = calendar.Calendar()
        first_year, last_year = start.year(), end.year()
        first_month, last_month = start.month(), end.month()

        weeks = []
        for year in range(first_year, last_year+1):
            # count from first month only for first year
            month_from = 1
            if year == first_year:
                month_from = first_month

            # count till last month only for last year
            month_to = 12
            if year == last_year:
                month_to = last_month

            for month in range(month_from, month_to+1):
                # loop over weeks in a month of the year
                for week in my_cal.monthdayscalendar(year, month):
                    # filter out zero days
                    temp = [d for d in week if d]
                    weeks.append((year, month, temp[0], temp[-1]))

        return weeks

    def _getMonthsRange(self, start, end):
        """Returns list of (year, month, last_day) tuples for passed
        start and end DateTimes.
        """
        first_year, last_year = start.year(), end.year()
        first_month, last_month = start.month(), end.month()

        months = []
        for year in range(first_year, last_year+1):
            # count from first month only for first year
            month_from = 1
            if year == first_year:
                month_from = first_month

            # count till last month only for last year
            month_to = 12
            if year == last_year:
                month_to = last_month

            for month in range(month_from, month_to+1):
                months.append((year, month,
                    calendar.monthrange(year, month)[1]))

        return months

    def getJSONLayer(self):
        return json.dumps({})

    @memoize
    def _get_markers(self, brain):
        """Return dict of marker details."""
        markers = []
        if brain.zgeo_geometry:
            markers.append({
                'uid': brain.UID,
                'search_uid': brain.UID,
                'url': brain.getURL(),
                'title': brain.Title,
                'tags': brain.Subject or [],
                'start': brain.start or '',
                'end': brain.end or '',
                'geometry': brain.zgeo_geometry,
                'latitude': brain.zgeo_geometry['coordinates'][1],
                'longitude': brain.zgeo_geometry['coordinates'][0],
            })
        return markers

