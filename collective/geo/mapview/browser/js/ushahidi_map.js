$(function() { $(document).pngFix(); });

OpenLayers.ImgPath = ushahidi_imagesLocation;

// Initialize the Ushahidi namespace
Ushahidi.baseUrl = ushahidi_baseUrl;
Ushahidi.markerRadius = ushahidi_markerRadius;
Ushahidi.markerOpacity = ushahidi_markerOpacity;
Ushahidi.markerStokeWidth = ushahidi_markerStokeWidth;
Ushahidi.markerStrokeOpacity = ushahidi_markerStrokeOpacity;

// Default to most active month
var startTime = ushahidi_startTime;

// Default to most active month
var endTime = ushahidi_endTime;

// To hold the Ushahidi.Map reference
var map = null;


/**
 * Callback function for rendering the timeline
 */
function refreshTimeline(options) {
  if (!ushahidi_enableTimeline) {
    return;
  }

  // Use report filters if no options passed
  options = options || map.getReportFilters();
  // Copy options object to avoid accidental modifications to reportFilters
  options = jQuery.extend({}, options);

  var url = ushahidi_baseUrl + '/@@ushahidi-timeline';

  var start = options.s, end = options.e;
  if (start == 0) {
    start = $("#startDate").val();
    startTime = start;
    options.s = start;
  }
  if (end == 0) {
    end = $("#endDate").val();
    endTime = end;
    options.e = end;
  }

  var interval = (end - start) / (3600 * 24);

  var dateFormat = '%#d&nbsp;%b<br />%Y';
  if (interval <= 3) {
    // TODO: not implemented on server side
    options.i = "hour";
  } else if (interval <= (31 * 2)) {
    options.i = "day";
    dateFormat = '&nbsp;%#d<br />%b';
  } else if (interval <= (31 * 6)) {
    options.i = "week";
    dateFormat = '&nbsp;%#d<br />%b';
  } else {
    options.i = "month";
  }

  // Get the graph data
  $.ajax({
    url: url,
    data: options,
    success: function(response) {
      // Clear out the any existing plots
      $("#graph").html('');

      if (response != null && response[0].data.length < 2)
        return;

      var graphData = [];
      var raw = response[0].data;
      for (var i=0; i<raw.length; i++) {
        var date = new Date(raw[i][0]);

        var dateStr = date.getFullYear() + "-";
        dateStr += ('0' + (date.getMonth()+1)).slice(-2) + '-';
        dateStr += ('0' + date.getDate()).slice(-2);

        graphData.push([dateStr, parseInt(raw[i][1])]);
      }
      var timeline = $.jqplot('graph', [graphData], {
        seriesDefaults: {
          color: response[0].color,
          lineWidth: 1.6,
          markerOptions: {
            show: false
          }
        },
        axesDefaults: {
          pad: 1.23,
        },
        axes: {
          xaxis: {
            renderer: $.jqplot.DateAxisRenderer,
            tickOptions: {
              formatString: dateFormat
            }
          },
          yaxis: {
            min: 0,
            tickOptions: {
              formatString: '%.0f'
            }
          }
        },
        cursor: {show: false}
      });
    },
    dataType: "json"
  });
}


jQuery(function() {
  var reportsURL = ushahidi_allowClustering ? "@@ushahidi-json-cluster" : "@@ushahidi-json";

  // Render thee JavaScript for the base layers so that
  // they are accessible by Ushahidi.js
  // TODO: make it configurable, for this we need to rewrite map.php to python
  var google_satellite = new OpenLayers.Layer.Google("Google Maps Satellite", {
    type: google.maps.MapTypeId.SATELLITE,
    animationEnabled: true,
    sphericalMercator: true,
    maxExtent: new OpenLayers.Bounds(-20037508.34, -20037508.34, 20037508.34,
      20037508.34)});

  var google_hybrid = new OpenLayers.Layer.Google("Google Maps Hybrid", {
    type: google.maps.MapTypeId.HYBRID,
    animationEnabled: true,
    sphericalMercator: true,
    maxExtent: new OpenLayers.Bounds(-20037508.34, -20037508.34, 20037508.34,
      20037508.34)});

  var google_normal = new OpenLayers.Layer.Google("Google Maps Normal", {
    animationEnabled: true,
    sphericalMercator: true,
    maxExtent: new OpenLayers.Bounds(-20037508.34, -20037508.34, 20037508.34,
      20037508.34)});

  var google_physical = new OpenLayers.Layer.Google("Google Maps Physical", {
    type: google.maps.MapTypeId.TERRAIN,
    animationEnabled: true,
    sphericalMercator: true,
    maxExtent: new OpenLayers.Bounds(-20037508.34, -20037508.34, 20037508.34,
      20037508.34)});
  
  // Map configuration
  var config = {

    // Zoom level at which to display the map
    zoom: ushahidi_defaultZoom,

    // Redraw the layers when the zoom level changes
    redrawOnZoom: ushahidi_allowClustering,

    // Center of the map
    center: {
      latitude: ushahidi_defaultLatitude,
      longitude: ushahidi_defaultLongitude
    },

    // Map controls
    mapControls: [
      new OpenLayers.Control.Navigation({ dragPanOptions: { enableKinetic: true } }),
      new OpenLayers.Control.Attribution(),
      new OpenLayers.Control.Zoom(),
      new OpenLayers.Control.MousePosition({
        div: document.getElementById('mapMousePosition'),
        numdigits: 5
      }),
      new OpenLayers.Control.Scale('mapScale'),
      new OpenLayers.Control.ScaleLine(),
      new OpenLayers.Control.LayerSwitcher()
    ],

    // Base layers
    // TODO: make it configurable
    baseLayers: [google_normal, google_satellite, google_hybrid,
      google_physical],

    // Display the map projection
    showProjection: true,
    
    reportFilters: {
      s: startTime,
      e: endTime
    }

  };

  // Initialize the map
  map = new Ushahidi.Map('map', config);
  map.addLayer(Ushahidi.GEOJSON, {
    name: ushahidi_mainLayerName,
    url: reportsURL,
    transform: false
  }, true, true);


  // Register the refresh timeline function as a callback
  map.register("filterschanged", refreshTimeline);
  setTimeout(function() { refreshTimeline({
    s: startTime,
    e: endTime
  }); }, 800);


  // Category Switch Action
  $("ul#category_switch li > a").click(function(e) {
    
    var categoryId = this.id.substring(4);
    var catSet = 'cat_' + this.id.substring(4);

    // Remove All active
    $("a[id^='cat_']").removeClass("active");
    
    // Hide All Children DIV
    $("[id^='child_']").hide();

    // Add Highlight
    $("#cat_" + categoryId).addClass("active"); 

    // Show children DIV
    $("#child_" + categoryId).show();
    $(this).parents("div").show();
    
    // Update report filters
    map.updateReportFilters({c: categoryId});

    e.stopPropagation();
    return false;
  });

  // Layer selection
  $("ul#kml_switch li > a").click(function(e) {
    // Get the layer id
    var layerId = this.id.substring(6);

    var isCurrentLayer = false;
    var context = this;

    // Remove all actively selected layers
    $("#kml_switch a").each(function(i) {
      if ($(this).hasClass("active")) {
        if (this.id == context.id) {
          isCurrentLayer = true;
        }
        map.trigger("deletelayer", $(".layer-name", this).html());
        $(this).removeClass("active");
      }
    });

    // Was a different layer selected?
    if (!isCurrentLayer) {
      // Set the currently selected layer as the active one
      $(this).addClass("active");
      map.addLayer(Ushahidi.KML, {
        name: $(".layer-name", this).html(),
        url: "@@ushahidi-json-layer?layer=" + layerId
      });
    }

    return false;
  });
    
  // Timeslider and date change actions
  if ($('select#startDate option').length > 0 &&
      $('select#endDate option').length > 0) {
    $("select#startDate, select#endDate").selectToUISlider({
      labels: 4,
      labelSrc: 'text',
      sliderOptions: {
        change: function(e, ui) {
          var from = $("#startDate").val();
          var to = $("#endDate").val();

          if (to > from && (from != startTime || to != endTime)) {
            // Update the report filters
            startTime = from;
            endTime = to;
            map.updateReportFilters({s: from, e: to});
          }

          e.stopPropagation();
        }
      }
    });
  };
  
  // Media Filter Action
  $('.filters li a').click(function() {
    var mediaType = this.id.replace('media_', '') || '';
    
    $('.filters li a').attr('class', '');
    $(this).addClass('active');

    // Update the report filters
    map.updateReportFilters({m: mediaType});

    return false;
  });

});
