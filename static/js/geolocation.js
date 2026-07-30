// Event form: "Use my location" fills the lat/lng fields via the
// browser's geolocation API, no Google Maps API key needed for this part.

document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('use-my-location');
  if (!btn) return;

  const latField = document.getElementById('id_latitude');
  const lngField = document.getElementById('id_longitude');

  btn.addEventListener('click', () => {
    if (!navigator.geolocation) {
      showToast('Geolocation is not supported by this browser.', 'error');
      return;
    }
    btn.disabled = true;
    btn.textContent = 'Locating…';
    navigator.geolocation.getCurrentPosition(
      (position) => {
        latField.value = position.coords.latitude.toFixed(6);
        lngField.value = position.coords.longitude.toFixed(6);
        btn.disabled = false;
        btn.textContent = 'Use my location';
        showToast('Location captured.');
      },
      (error) => {
        btn.disabled = false;
        btn.textContent = 'Use my location';
        showToast(`Could not get location: ${error.message}`, 'error');
      },
    );
  });
});
