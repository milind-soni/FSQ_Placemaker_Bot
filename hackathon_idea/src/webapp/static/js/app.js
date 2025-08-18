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
        container.innerHTML = `
            <div style="text-align:center; color:#aaa; margin-top: 2rem;">
                <h3>🔍 No places found</h3>
                <p>Try adjusting your filters or search for places using the PlacePilot Telegram bot!</p>
                <a href="https://t.me/your_bot_username" style="color: #6cb3fa; text-decoration: none;">
                    Open PlacePilot Bot →
                </a>
            </div>
        `;
        return;
    }
    
    container.innerHTML = '';
    places.forEach((place, index) => {
        const name = place.name || 'Unknown Place';
        const rating = place.rating !== undefined && place.rating !== null ? `${place.rating} ⭐` : 'N/A';
        const price = place.price !== undefined && place.price !== null ? '$'.repeat(Number(place.price)) : 'N/A';
        const openNow = place.hours && typeof place.hours.open_now === 'boolean' ? place.hours.open_now : null;
        const status = openNow === true ? 'Open' : openNow === false ? 'Closed' : 'Unknown';
        const statusClass = openNow === true ? 'open' : openNow === false ? 'closed' : '';
        const distance = place.distance !== undefined && place.distance !== null ? `${place.distance}m` : 'N/A';
        const imgSrc = place.image_url ? place.image_url : '/static/images/placeholder.png';
        const categories = place.categories && place.categories.length > 0 ? place.categories.join(', ') : '';

        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <img class="card-img" src="${imgSrc}" alt="Place image" onerror="this.onerror=null;this.src='/static/images/placeholder.png';">
            <div class="card-content">
                <div class="card-title">${name}</div>
                ${categories ? `<div class="card-category">${categories}</div>` : ''}
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

function showWelcomeMessage() {
    const container = document.getElementById('list-container');
    container.innerHTML = `
        <div style="text-align:center; color:#f0f0f0; margin-top: 2rem; padding: 2rem;">
            <h2 style="color: #6cb3fa; margin-bottom: 1rem;">🤖 Welcome to PlacePilot!</h2>
            <p style="margin-bottom: 1.5rem;">Your AI-powered location companion</p>
            
            <div style="background: #2d2d2d; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem;">
                <h3 style="color: #6cb3fa; margin-top: 0;">What can I do?</h3>
                <div style="text-align: left;">
                    <p>🔍 <strong>Find Places:</strong> Search for restaurants, cafes, shops, and more</p>
                    <p>🧠 <strong>Get Recommendations:</strong> Personalized suggestions based on your preferences</p>  
                    <p>📝 <strong>Contribute Data:</strong> Add new places and update information</p>
                </div>
            </div>
            
            <div style="margin-bottom: 1.5rem;">
                <h4 style="color: #6cb3fa;">Get Started:</h4>
                <p>Search for places by talking to the PlacePilot Telegram bot!</p>
            </div>
            
            <a href="https://t.me/your_bot_username" 
               style="display: inline-block; background: #6cb3fa; color: white; padding: 12px 24px; 
                      border-radius: 25px; text-decoration: none; font-weight: bold; margin: 0.5rem;">
                🚀 Open PlacePilot Bot
            </a>
        </div>
    `;
}

window.onload = function() {
    // Check if we have places data injected from backend
    if (window.hasData && window.placesData) {
        try {
            allPlaces = Array.isArray(window.placesData) ? window.placesData : JSON.parse(window.placesData);
            filteredPlaces = [...allPlaces];
            setupFilters();
            renderList(filteredPlaces);
        } catch (e) {
            console.error('Error parsing places data:', e);
            showWelcomeMessage();
        }
    } else {
        // Fallback to URL parameter method
        const dataParam = getQueryParam('data');
        if (dataParam) {
            allPlaces = decodeData(dataParam);
            filteredPlaces = [...allPlaces];
            setupFilters();
            renderList(filteredPlaces);
        } else {
            showWelcomeMessage();
        }
    }
}; 