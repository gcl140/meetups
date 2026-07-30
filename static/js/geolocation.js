// Event form: "Use my location" fills the (hidden) lat/lng fields via the
// browser's geolocation API, no Google Maps API key needed for this part.
// A small status line + "Clear" link give feedback since the raw
// coordinate inputs themselves aren't shown in the layout.
//
// Exposed as window.initGeolocationButton(root) so the edit modal can
// re-run this after swapping in fresh form HTML fetched after
// DOMContentLoaded already fired.

function initGeolocationButton(root = document) {
  const btn = root.querySelector('#use-my-location');
  if (!btn || btn.dataset.geoBound) return;
  btn.dataset.geoBound = 'true';

  const latField = root.querySelector('#id_latitude');
  const lngField = root.querySelector('#id_longitude');
  const status = root.querySelector('#location-status');
  const statusText = status?.querySelector('span');
  const clearBtn = root.querySelector('#clear-location');
  const originalLabel = btn.innerHTML;

  function renderStatus() {
    const hasCoords = latField.value && lngField.value;
    status?.classList.toggle('hidden', !hasCoords);
    clearBtn?.classList.toggle('hidden', !hasCoords);
    if (hasCoords && statusText) {
      statusText.textContent = `Coordinates set (${Number(latField.value).toFixed(4)}, ${Number(lngField.value).toFixed(4)})`;
    }
  }

  btn.addEventListener('click', () => {
    if (!navigator.geolocation) {
      showToast('Geolocation is not supported by this browser.', 'error');
      return;
    }
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Locating…';
    navigator.geolocation.getCurrentPosition(
      (position) => {
        latField.value = position.coords.latitude.toFixed(6);
        lngField.value = position.coords.longitude.toFixed(6);
        btn.disabled = false;
        btn.innerHTML = originalLabel;
        renderStatus();
        showToast('Location captured.');
      },
      (error) => {
        btn.disabled = false;
        btn.innerHTML = originalLabel;
        showToast(`Could not get location: ${error.message}`, 'error');
      },
    );
  });

  clearBtn?.addEventListener('click', () => {
    latField.value = '';
    lngField.value = '';
    renderStatus();
  });

  renderStatus();
}

window.initGeolocationButton = initGeolocationButton;
document.addEventListener('DOMContentLoaded', () => initGeolocationButton(document));
