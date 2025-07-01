function getQueryParam(name) {
    const url = new URL(window.location.href);
    return url.searchParams.get(name);
}

function decodeData(data) {
    try {
        const json = atob(data.replace(/-/g, '+').replace(/_/g, '/'));
        return JSON.parse(json);
    } catch (e) {
        return [];
    }
}

function renderList(places) {
    const container = document.getElementById('list-container');
    if (!places.length) {
        container.innerHTML = '<div style="text-align:center; color:#aaa;">No places to display.</div>';
        return;
    }
    container.innerHTML = '';
    places.forEach(place => {
        const name = place.name || 'Unknown Place';
        const rating = place.rating !== undefined && place.rating !== null ? `${place.rating} \u2b50` : 'N/A';
        const price = place.price !== undefined && place.price !== null ? '$'.repeat(Number(place.price)) : 'N/A';
        const openNow = place.hours && typeof place.hours.open_now === 'boolean' ? place.hours.open_now : null;
        const status = openNow === true ? 'Open' : openNow === false ? 'Closed' : 'Unknown';
        const statusClass = openNow === true ? 'open' : openNow === false ? 'closed' : '';
        const distance = place.distance !== undefined && place.distance !== null ? `${place.distance}m` : 'N/A';
        const imgSrc = place.image_url ? place.image_url : 'placeholder.png';

        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <img class="card-img" src="${imgSrc}" alt="Place image" onerror="this.onerror=null;this.src='placeholder.png';">
            <div class="card-content">
                <div class="card-title">${name}</div>
                <div class="card-row">
                    <span class="card-rating">${rating}</span>
                    <span class="card-price">${price}</span>
                </div>
                <div class="card-row">
                    <span class="card-status ${statusClass}">${status}</span>
                    <span class="card-distance">${distance} away</span>
                </div>
            </div>
        `;
        container.appendChild(card);
    });
}

window.onload = function() {
    const dataParam = getQueryParam('data');
    if (!dataParam) {
        renderList([]);
        return;
    }
    const places = decodeData(dataParam);
    renderList(places);
}; 