from zope.publisher.browser import BrowserView

from Products.CMFCore.utils import getToolByName


DEFAULT_MARKER_COLOR = 'CC0000'

# TODO: make below settings configurable via Ushahidi Settings tab
# on folderish objects
TEMPLATE = """\
var ushahidi_baseUrl = '%(baseUrl)s'; // context.absolute_url()
var ushahidi_imagesLocation = '%(imagesLocation)s'; // ++resource++collective...
var ushahidi_markerRadius = %(markerRadius)s; // 4
var ushahidi_markerOpacity = %(markerOpacity)s; // 0.8
var ushahidi_markerStokeWidth = %(markerStokeWidth)s; // 2
var ushahidi_markerStrokeOpacity = %(markerStrokeOpacity)s; // 0.3
var ushahidi_startTime = %(startTime)s; // 1333238400 $active_startDate
var ushahidi_endTime = %(endTime)s; // 1359676799 $active_endDate
var ushahidi_enableTimeline = %(enableTimeline)s; // true
var ushahidi_allowClustering = %(allowClustering)s; // true
var ushahidi_defaultZoom = %(defaultZoom)s; // 7
var ushahidi_defaultLatitude = %(defaultLatitude)s; // -1.2873000707050097
var ushahidi_defaultLongitude = %(defaultLongitude)s; // 36.821451182008204
var ushahidi_mainLayerName = '%(mainLayerName)s'; // Reports
var ushahidi_defaultMap = '%(defaultMap)s'; // osm_mapnik
"""


class JSVariables(BrowserView):

    def __call__(self, *args, **kwargs):
        context = self.context
        response = self.request.response
        response.setHeader('content-type', 'text/javascript; charset=utf-8')

        url = context.absolute_url()
        purl = getToolByName(context, 'portal_url')()

        return TEMPLATE % dict(
            baseUrl=url,
            markerRadius='4',
            markerOpacity='0.8',
            markerStokeWidth='2',
            markerStrokeOpacity='0.3',
            startTime='0',
            endTime='0',
            enableTimeline='true',
            allowClustering='true',
            defaultZoom='7',
            # TODO: make map auto-center
            defaultLatitude='23.69781',
            defaultLongitude='120.96051499999999',
            mainLayerName=context.Title(),
            defaultMap='osm_mapnik',
            imagesLocation='%s/++resource++collective.geo.mapview.img/' % purl,
        )

