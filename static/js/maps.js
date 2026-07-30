// Embedded Google Map on the event detail page. Only loaded when the
// template has both a GOOGLE_MAPS_API_KEY configured and the event has
// lat/lng set, see events/event_detail.html for the conditional script tag.

function initMap() {
  const el = document.getElementById('map-canvas');
  if (!el) return;

  const lat = parseFloat(el.dataset.lat);
  const lng = parseFloat(el.dataset.lng);
  if (Number.isNaN(lat) || Number.isNaN(lng)) return;

  const woodMapStyle = [
    { elementType: 'geometry', stylers: [{ color: '#f2e8dc' }] },
    { elementType: 'labels.text.stroke', stylers: [{ color: '#faf6f1' }] },
    { elementType: 'labels.text.fill', stylers: [{ color: '#4d2f1c' }] },
    { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#c08a56' }] },
    { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#e4cdb0' }] },
    { featureType: 'poi', elementType: 'geometry', stylers: [{ color: '#f2e8dc' }] },
    { featureType: 'landscape', elementType: 'geometry', stylers: [{ color: '#fbf1e2' }] },
  ];

  const center = { lat, lng };
  const map = new google.maps.Map(el, {
    center,
    zoom: 15,
    styles: woodMapStyle,
    disableDefaultUI: true,
    zoomControl: true,
  });

  new google.maps.Marker({
    position: center,
    map,
    title: el.dataset.title || 'Event location',
  });
}
