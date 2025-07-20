let allPlaces = [];
let filteredPlaces = [];
let filters = {
    openNow: false,
    topRated: false,
    price: 'all'
};

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

function applyFilters() {
    filteredPlaces = allPlaces.filter(place => {
        // Open Now filter
        if (filters.openNow) {
            const openNow = place.hours && place.hours.open_now;
            if (!openNow) return false;
        }
        
        // Top Rated filter (8+ stars)
        if (filters.topRated) {
            const rating = place.rating;
            if (!rating || rating < 8) return false;
        }
        
        // Price filter
        if (filters.price !== 'all') {
            const targetPrice = parseInt(filters.price);
            if (place.price !== targetPrice) return false;
        }
        
        return true;
    });
    
    renderList(filteredPlaces);
}

function togglePill(pillId, filterKey) {
    const pill = document.getElementById(pillId);
    const isActive = pill.classList.contains('active');
    
    if (isActive) {
        pill.classList.remove('active');
        filters[filterKey] = false;
    } else {
        pill.classList.add('active');
        filters[filterKey] = true;
    }
    
    applyFilters();
}

function setupFilters() {
    // Price dropdown
    document.getElementById('priceFilter').addEventListener('change', function() {
        filters.price = this.value;
        applyFilters();
    });
    
    // Open Now toggle pill
    document.getElementById('openNowPill').addEventListener('click', function() {
        togglePill('openNowPill', 'openNow');
    });
    
    // Top Rated toggle pill
    document.getElementById('topRatedPill').addEventListener('click', function() {
        togglePill('topRatedPill', 'topRated');
    });
}

function renderList(places) {
    const container = document.getElementById('list-container');
    if (!places.length) {
        container.innerHTML = '<div style="text-align:center; color:#aaa; margin-top: 2rem;">No places match your filters.</div>';
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
    allPlaces = decodeData(dataParam);
    filteredPlaces = [...allPlaces];
    setupFilters();
    renderList(filteredPlaces);
}; 