#!/usrbin/env python

import json
import calendar

from Acquisition import aq_inner

from zope.interface import implements
from zope.component import getMultiAdapter, getUtility

from Products.Five.browser import BrowserView
from Products.CMFCore.utils import getToolByName
from Products.ATContentTypes.utils import DT2dt
from Products.AdvancedQuery import Eq, In, Between

from plone.memoize.instance import memoize
from plone.registry.interfaces import IRegistry

from .interfaces import IUshahidiMapView
from .map_settings_js import DEFAULT_MARKER_COLOR

from plone.memoize import ram

START_YEAR = 1840
END_YEAR = 1960
CACHE_MIN = 60


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

        categories = set()  # to store unique object keywords
        ctypes = []  # to store portal type and it's title
        ctypes_added = []  # to avoid duplicates in content types list
        ctypes_meta = {}  # to cache portal type Titles

        query = Eq('path', '/'.join(context.getPhysicalPath())) & \
            In('portal_type', self.friendly_types()) & \
            Eq('object_provides',
                'collective.geo.geographer.interfaces.IGeoreferenceable')

        brains = catalog.evalAdvancedQuery(query, (('yearHist', 'asc'),))
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
        ctypes.sort(lambda x, y: cmp(x['title'], y['title']))

        # prepare dates, for this we just generate range of years
        # between first and last item fetched list of objects
        dates = []
        first_year = None
        if len(brains) > 0:
            # skip object w/o set start date
            for brain in brains:
                # skip if no coordinates set
                markers = self._get_markers(brain)
                if not markers:
                    continue

                if brain.yearHist:
                    first_year = brain.yearHist
                    break

            if first_year:
                # now try to find last date, based on end field
                for brain in catalog.evalAdvancedQuery(query,
                        (('yearHist', 'desc'),)):
                    # skip if no coordinates set
                    markers = self._get_markers(brain)
                    if not markers:
                        continue

                    if brain.yearHist:
                        last_year = brain.yearHist
                        break

                if first_year and last_year:
                    for year in range(first_year, last_year+1):
                        dates.append(year)

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
        start, end = self.get_period()
        if start and end:
            query &= Between('yearHist', int(start), int(end), filter=False)

        return query

    def get_period(self):
        try:
            start = int(self.request['s'])
        except:
            start = START_YEAR
        try:
            end = int(self.request['e'])
        except:
            if start < END_YEAR:
                end = END_YEAR
            else:
                end = start

        return start, end

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
        for brain in catalog.evalAdvancedQuery(query, (('yearHist', 'asc'), )):
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

        return json.dumps({"type": "FeatureCollection", "features": features})

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

    #@ram.cache(lambda *args: time() // (60 * CACHE_MIN))
    def getTimelineMarkers(self):
        markers = []
        query = self._prepare_query()
        catalog = getToolByName(self.context, 'portal_catalog')
        for brain in catalog.evalAdvancedQuery(query, (('yearHist', 'asc'),)):

            # skip if no coordinates set
            has_markers = self._get_markers(brain)
            if not has_markers:
                continue

            # skip if there is no valid start date set
            if not brain.yearHist:
                continue

            markers.append(brain)
        return markers

    def getTimeline(self):
        data = []
        markers = self.getTimelineMarkers()

        # prepare data from request
        start, end = self.get_period()

        years = {}
        for year in range(start, end+1):
            years.setdefault(year, 0)
            for marker in markers:
                if marker.yearHist == year:
                    years[year] += 1

        # sort and filter out 'zero' months
        keys = years.keys()
        keys.sort()
        data = [[key, years[key]] for key in keys]

        return json.dumps([{
            "label": self.request.get('c', '') or "All Categories",
            "color": self._get_category_color(),
            "data": data
        }])

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
