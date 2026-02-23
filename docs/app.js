// Daytime Magnet - Main Application

// Global data stores
let commuterData = null;
let countyList = null;
let selectedCountyFips = null;
let commuterChart = null;

// DOM Elements
const countySearch = document.getElementById('county-search');
const autocompleteList = document.getElementById('autocomplete-list');
const searchBtn = document.getElementById('search-btn');
const resultsDiv = document.getElementById('results');
const errorDiv = document.getElementById('error');
const exampleBtns = document.querySelectorAll('.example-btn');

// Initialize
async function init() {
    try {
        const [dataResponse, listResponse] = await Promise.all([
            fetch('data/commuter_data.json'),
            fetch('data/county_list.json')
        ]);

        commuterData = await dataResponse.json();
        countyList = await listResponse.json();

        console.log(`Loaded ${Object.keys(commuterData).length} counties`);

        setupEventListeners();
    } catch (error) {
        console.error('Failed to load data:', error);
        showError('Failed to load data. Please refresh the page.');
    }
}

function setupEventListeners() {
    countySearch.addEventListener('input', handleCountyInput);
    countySearch.addEventListener('focus', () => {
        if (countySearch.value.length >= 2) {
            showAutocomplete(countySearch.value);
        }
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.input-group')) {
            autocompleteList.classList.remove('active');
        }
    });

    countySearch.addEventListener('keydown', handleAutocompleteKeydown);

    searchBtn.addEventListener('click', handleSearch);

    countySearch.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !autocompleteList.classList.contains('active')) {
            handleSearch();
        }
    });

    exampleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const county = btn.dataset.county;
            selectedCountyFips = county;
            const countyData = commuterData[county];
            if (countyData) {
                countySearch.value = countyData.name;
            }
            handleSearch();
        });
    });
}

function handleCountyInput(e) {
    const query = e.target.value.trim();
    selectedCountyFips = null;

    if (query.length < 2) {
        autocompleteList.classList.remove('active');
        return;
    }

    showAutocomplete(query);
}

function showAutocomplete(query) {
    const queryLower = query.toLowerCase();

    const matches = countyList
        .filter(c => c.name.toLowerCase().includes(queryLower))
        .slice(0, 10);

    if (matches.length === 0) {
        autocompleteList.classList.remove('active');
        return;
    }

    autocompleteList.innerHTML = matches.map((c, i) => `
        <div class="autocomplete-item" data-fips="${c.fips}" data-index="${i}">
            <span class="county-name">${c.name}</span>
        </div>
    `).join('');

    autocompleteList.querySelectorAll('.autocomplete-item').forEach(item => {
        item.addEventListener('click', () => {
            const fips = item.dataset.fips;
            const county = commuterData[fips];
            if (county) {
                countySearch.value = county.name;
                selectedCountyFips = fips;
            }
            autocompleteList.classList.remove('active');
        });
    });

    autocompleteList.classList.add('active');
}

function handleAutocompleteKeydown(e) {
    if (!autocompleteList.classList.contains('active')) return;

    const items = autocompleteList.querySelectorAll('.autocomplete-item');
    const currentIndex = Array.from(items).findIndex(item => item.classList.contains('selected'));

    if (e.key === 'ArrowDown') {
        e.preventDefault();
        const nextIndex = currentIndex < items.length - 1 ? currentIndex + 1 : 0;
        items.forEach((item, i) => item.classList.toggle('selected', i === nextIndex));
        items[nextIndex].scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prevIndex = currentIndex > 0 ? currentIndex - 1 : items.length - 1;
        items.forEach((item, i) => item.classList.toggle('selected', i === prevIndex));
        items[prevIndex].scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'Enter') {
        e.preventDefault();
        const selectedItem = autocompleteList.querySelector('.autocomplete-item.selected');
        if (selectedItem) {
            selectedItem.click();
        }
    } else if (e.key === 'Escape') {
        autocompleteList.classList.remove('active');
    }
}

function handleSearch() {
    hideError();

    if (!selectedCountyFips) {
        const searchText = countySearch.value.trim().toLowerCase();
        const match = countyList.find(c => c.name.toLowerCase() === searchText);
        if (match) {
            selectedCountyFips = match.fips;
        } else {
            showError('Please select a county from the dropdown.');
            return;
        }
    }

    const data = commuterData[selectedCountyFips];
    if (!data) {
        showError('No data available for this county.');
        return;
    }

    displayResults(selectedCountyFips, data);
}

function loadCounty(fips) {
    const data = commuterData[fips];
    if (!data) return;

    selectedCountyFips = fips;
    countySearch.value = data.name;
    displayResults(fips, data);

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function displayResults(fips, data) {
    // County title
    document.getElementById('county-title').textContent = data.name;

    // Hero stat - swing value
    const swingEl = document.getElementById('swing-value');
    const sign = data.net_swing_pct >= 0 ? '+' : '';
    swingEl.textContent = `${sign}${data.net_swing_pct}%`;
    swingEl.className = 'swing-value ' + (
        data.net_swing_pct > 5 ? 'positive' :
        data.net_swing_pct < -5 ? 'negative' : 'neutral'
    );

    // Classification badge
    const badge = document.getElementById('classification-badge');
    badge.textContent = data.classification;
    badge.className = 'classification-badge ' + (
        data.classification === 'Job Magnet' ? 'badge-magnet' :
        data.classification === 'Bedroom Community' ? 'badge-bedroom' : 'badge-self-contained'
    );

    // Percentile bar
    const pct = data.percentile;
    document.getElementById('percentile-fill').style.width = pct + '%';
    document.getElementById('percentile-text').textContent =
        `${pct}th percentile — higher swing than ${pct}% of U.S. counties`;

    // Stats row
    document.getElementById('employed-here').textContent = data.employed_here.toLocaleString();
    document.getElementById('live-here').textContent = data.live_here.toLocaleString();
    document.getElementById('internal').textContent = data.internal.toLocaleString();

    // Diverging bar chart
    renderCommuterChart(data);

    // Flow tables
    renderFlowTables(data);

    // Insight callout
    renderInsight(data);

    // Small county notice
    const noticeEl = document.getElementById('small-county-notice');
    if (data.small_county) {
        noticeEl.classList.remove('hidden');
    } else {
        noticeEl.classList.add('hidden');
    }

    // Show results
    resultsDiv.classList.remove('hidden');
    resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderCommuterChart(data) {
    const ctx = document.getElementById('commuter-chart').getContext('2d');

    if (commuterChart) {
        commuterChart.destroy();
    }

    commuterChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [''],
            datasets: [
                {
                    label: 'Out-Commuters',
                    data: [-data.out_commuters],
                    backgroundColor: '#818cf8',
                    borderRadius: 4
                },
                {
                    label: 'Internal',
                    data: [data.internal],
                    backgroundColor: '#d1d5db',
                    borderRadius: 4
                },
                {
                    label: 'In-Commuters',
                    data: [data.in_commuters],
                    backgroundColor: '#f59e0b',
                    borderRadius: 4
                }
            ]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const val = Math.abs(context.parsed.x);
                            return `${context.dataset.label}: ${val.toLocaleString()}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    stacked: true,
                    grid: { color: 'rgba(0, 0, 0, 0.05)' },
                    ticks: {
                        callback: function(value) {
                            const abs = Math.abs(value);
                            if (abs >= 1e6) return (abs / 1e6).toFixed(1) + 'M';
                            if (abs >= 1e3) return (abs / 1e3).toFixed(0) + 'K';
                            return abs;
                        }
                    }
                },
                y: {
                    stacked: true,
                    display: false
                }
            }
        }
    });
}

function renderFlowTables(data) {
    const originsTable = document.getElementById('origins-table');
    const destsTable = document.getElementById('destinations-table');

    originsTable.innerHTML = data.top_origins
        .map((flow, i) => `
            <tr>
                <td>${i + 1}</td>
                <td class="county-link" data-fips="${flow.fips}">${flow.name}</td>
                <td>${flow.workers.toLocaleString()}</td>
            </tr>
        `).join('');

    destsTable.innerHTML = data.top_destinations
        .map((flow, i) => `
            <tr>
                <td>${i + 1}</td>
                <td class="county-link" data-fips="${flow.fips}">${flow.name}</td>
                <td>${flow.workers.toLocaleString()}</td>
            </tr>
        `).join('');

    // Add click handlers for county links
    document.querySelectorAll('.county-link').forEach(link => {
        link.addEventListener('click', () => {
            const fips = link.dataset.fips;
            if (fips && commuterData[fips]) {
                loadCounty(fips);
            }
        });
    });
}

function renderInsight(data) {
    const callout = document.getElementById('insight-callout');
    const swing = data.net_swing_pct;
    const name = data.name.split(',')[0]; // Just county name without state
    let text, className;

    if (swing > 20) {
        text = `${name} is a major job magnet. Its daytime workforce swells by ${swing}% as workers pour in from surrounding counties. This signals a dense employment center — think office corridors, hospital complexes, or government hubs.`;
        className = 'insight-magnet';
    } else if (swing > 5) {
        text = `${name} draws more workers in than it sends out, making it a net job magnet. The +${swing}% swing suggests meaningful employment concentration beyond just serving local residents.`;
        className = 'insight-magnet';
    } else if (swing > -5) {
        text = `${name} is roughly self-contained — the number of workers commuting in and out is balanced. This typically indicates a mix of local employment and some cross-county commuting in both directions.`;
        className = 'insight-balanced';
    } else if (swing > -20) {
        text = `${name} is a bedroom community — more residents leave for work than workers come in. The ${swing}% swing suggests many residents commute to neighboring job centers.`;
        className = 'insight-bedroom';
    } else {
        text = `${name} is a strong bedroom community. With a ${swing}% daytime swing, a large share of residents commute out to work elsewhere, while relatively few jobs draw workers in.`;
        className = 'insight-bedroom';
    }

    callout.className = 'insight-callout ' + className;
    callout.innerHTML = `<span class="insight-text">${text}</span>`;
}

function showError(message) {
    errorDiv.textContent = message;
    errorDiv.classList.remove('hidden');
    resultsDiv.classList.add('hidden');
}

function hideError() {
    errorDiv.classList.add('hidden');
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', init);
