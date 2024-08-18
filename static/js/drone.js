let map;

var centerX = [27.535378, 37.7045823];
var centerY = [-80.351586, -89.4585105];
var zoomMap = 19;
var droneSize = 44;

var list_pos = [];
var cur_i = -1;
var missions = [];
var solidLine, droneLine;
var drone_pos = new google.maps.LatLng(centerX[0],centerY[0]);
var arming = true;
var gcs_counter = 3;

function formattedTime(seconds){
    let mins = Math.floor(seconds / 60);
    let secs = seconds - mins * 60;
    let smins = mins.toString();
    let ssecs = secs.toString();
    if (mins < 10)
        smins = "0" + smins;
    if (secs < 10)
        ssecs = "0" + ssecs;
    return smins + ":" + ssecs;
}
function GCSColor(element, previous, current){
    // console.log(gcs_counter);
    if (previous == current)
        gcs_counter += 1;
    else
        gcs_counter = 0;

    if (gcs_counter > 3){
        element.textContent= "GCS DISCONNECTED";
        element.style.color='red';
    }
    else{
        element.textContent = "GCS CONNECTED";
        element.style.color='green';
    }
    

}
function batteryColor(element){
    if (element.textContent < 14.7)
        element.style.color = 'red';
    else
        element.style.color = 'black';
}
function doColor(element){
    if (element.textContent < 1)
        element.style.color = 'red';
    else
        element.style.color = 'black';
}
function msgColor(element){
    if (element.value <= 2)
        element.style.color = 'red';
    else if (element.value <= 4)
        element.style.color = 'orange';
    else
        element.style.color = 'black';
}
function timerColor(element){
    if (element.value > 5)
        element.style.color = 'red';
    else
        element.style.color = 'black';
}
function updateData(){
    fetch('/data/LH_Farm drone ' + drone_id)
        .then(response => response.json())
        .then(json => {
        if (json) {

            for (var key in json.data){
            if (key.split('_').pop() == "time"){
                document.getElementById(key).textContent = formattedTime(json.data[key]);
            }
            else if (key == 'msg_severity'){
                document.getElementById('msg').value = json.data[key];
            }
            else if (key != "timers") {
                document.getElementById(key).textContent = json.data[key];
            }
            }
            //handle timers
            var oldGCS = document.getElementById('GCS_HBEAT').value;
            document.getElementById('GCS_HBEAT').value = json.data.timers.GCS_HBEAT;
            document.getElementById('GLOBAL_POSITION_INT').textContent = 'Position';
            document.getElementById('GLOBAL_POSITION_INT').value = json.data.timers.GLOBAL_POSITION_INT;
            document.getElementById('BATTERY_STATUS').textContent = 'Battery';
            document.getElementById('BATTERY_STATUS').value = json.data.timers.BATTERY_STATUS;
            document.getElementById('NAMED_VALUE_FLOAT').textContent = 'Payload';
            document.getElementById('NAMED_VALUE_FLOAT').value = json.data.timers.NAMED_VALUE_FLOAT;
            timerColor(document.getElementById('GLOBAL_POSITION_INT'));
            timerColor(document.getElementById('BATTERY_STATUS'));
            timerColor(document.getElementById('NAMED_VALUE_FLOAT'));
            // HANDLE COLOR CHANGES

            GCSColor(document.getElementById('GCS_HBEAT'), oldGCS, json.data.timers.GCS_HBEAT);
            batteryColor(document.getElementById('voltage'));
            doColor(document.getElementById('p_DO'));
            msgColor(document.getElementById('msg'));
            
            // HANDLE MISSION CHANGES
            missions = [];
            var landmarks = json.mission;
            for (var i = 0; i < landmarks.length; i++) {
                var lat = landmarks[i][0];
                var lon = landmarks[i][1];
                var mission = new google.maps.LatLng(lat,lon);
                missions.push(mission);
            }
            // HANDLE DRONE POSITION
            var dp = new google.maps.LatLng(json.data.lat, json.data.lon);
            if (!arePositionsEqual(drone_pos, dp)){
                drone_pos = dp;
                list_pos.push(drone_pos);
                if (list_pos.length > 30){
                    list_pos.shift();
                }
            }
            // UPDATE MAP WITH NEW MISSION & POS
            updatemap();
        }
        })
        .catch(function(){
        document.getElementById('GCS_HBEAT').textContent = "NO INTERNET";
        document.getElementById('GCS_HBEAT').style.color='red';
        })
}

function myMap() {
    var mapProp = {
        center: drone_pos,
        zoom:zoomMap,
        mapTypeId: 'satellite',
        mapTypeControl: false,
        fullscreenControl: true,
        streetViewControl: false,
        tilt: 0,

    };
    map = new google.maps.Map(document.getElementById("googleMap"), mapProp);


    droneLine = new google.maps.Polyline({
        path: list_pos,  // This is your array of google.maps.LatLng objects
        geodesic: true,  // If you want the shortest path over the earth's surface
        strokeColor: '#FF5500',  // Any color you want for the line
        strokeOpacity: 1.0,
        strokeWeight: 2,
        map: map,
    });

    drone = new google.maps.Marker({
      position: mapProp.center,
      icon: {
        url: "/static/images/drone.svg",
        scaledSize: new google.maps.Size(droneSize,droneSize),
        anchor: new google.maps.Point(droneSize / 2, droneSize / 2)
      }
    });
    drone.setMap(map);

    var lineSymbol = {
        path: google.maps.SymbolPath.FORWARD_CLOSED_ARROW
    };

    solidLine = new google.maps.Polyline({
        path: missions,  // This is your array of google.maps.LatLng objects
        geodesic: true,  // If you want the shortest path over the earth's surface
        strokeColor: '#FFFF00',  // Any color you want for the line
        strokeOpacity: 1.0,
        strokeWeight: 2,
        icons: [{
            icon: lineSymbol,
            offset: '100%',  // Position at the end of the line
            repeat: '100px'  // Change this value to control the spacing of arrows
        }],
        map: map
    });

    // Create the initial InfoWindow.
    let infoWindow = new google.maps.InfoWindow({
      content: "Click the map to get Lat/Lng!",
      position: mapProp.center,
    });
    map.addListener('mousemove', function(event) {
        var mouse_latlon = event.latLng;
        var levelZoom = 20 - map.getZoom();
        levelZoom = Math.pow(2, levelZoom);
        var i, shortest = Number.MAX_VALUE, si = -1;
        for (i = 0; i < list_pos.length; i++) {
            var dist = calculateDistance(mouse_latlon, list_pos[i]);
            if (dist < shortest && dist < levelZoom) {
                shortest = dist;
                si = i;
            }
        }

        if (si >= 0 && cur_i !== si) {
            if (cur_i >= 0) {
                infoWindow.close();
            }
            infoWindow = new google.maps.InfoWindow({
                position: list_pos[si],
                content: JSON.stringify(list_pos[si].toJSON(), null, 2)
            });
            infoWindow.open(map);
            cur_i = si;
        } else if (si < 0 && cur_i >= 0) {
            infoWindow.close();
            cur_i = -1;
        }
    });
}

function arePositionsEqual(pos1, pos2) {
  if (pos1 && pos2)
    return pos1.lat() === pos2.lat() && pos1.lng() === pos2.lng();
  return false;
}

function calculateDistance(pos1, pos2) {
    function toRadians(degrees) {
        return degrees * Math.PI / 180;
    }

    var R = 6371; // Radius of the Earth in kilometers
    var dLat = toRadians(pos2.lat() - pos1.lat());
    var dLon = toRadians(pos2.lng() - pos1.lng());
    var a = 
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(toRadians(pos1.lat())) * Math.cos(toRadians(pos2.lat())) * 
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
    var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    var distance = R * c; // Distance in kilometers
    return distance * 1000; // Convert distance to meters
}

function updatemap(){
    solidLine.setPath(missions);
    drone.setPosition(drone_pos);
        
    if (list_pos.length > 0){
        droneLine.setPath(list_pos);
    }
    
    if (map){
        map.setCenter(drone_pos);
    }
}

function loadMapWithId(id) {
    window.myMapWithId = function() {
        myMap();
    };
    var script = document.createElement('script');
    script.src = "https://maps.googleapis.com/maps/api/js?key=AIzaSyCQZZk_BUDTJwYN2TCsPwVJGLxkiMiSzPg&callback=myMapWithId";
    document.body.appendChild(script);
}
function loadMap() {
    window.myMapWithId = function() {
        myMap();
    };
    var script = document.createElement('script');
    script.src = "https://maps.googleapis.com/maps/api/js?key=AIzaSyCQZZk_BUDTJwYN2TCsPwVJGLxkiMiSzPg&callback=myMapWithId";
    document.body.appendChild(script);
}

// Useful code in future, do not delete
// map.addListener('click', function(event) {
//   var mouse_latlon = event.latLng;
//   list_pos.push(mouse_latlon);

//   drone.setPosition(mouse_latlon);
//   dashedLine.setPath(list_pos);
//   map.setCenter(mouse_latlon);
// });