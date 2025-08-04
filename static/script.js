document.addEventListener('DOMContentLoaded', () => {

    const map = L.map('map', { attributionControl: false }).setView([8.78, 78.13], 10);
    map.setMaxBounds([[8.3, 77.7], [9.3, 78.4]]);

    const googleSatellite = L.gridLayer.googleMutant({ type: 'satellite', maxZoom: 20 }).addTo(map);
    const googleRoadmap = L.gridLayer.googleMutant({ type: 'roadmap', maxZoom: 20 });
    L.control.layers({ "Google Satellite": googleSatellite, "Google Maps": googleRoadmap }).addTo(map);

    const crimeStyles = {
        'Fighting / Threatening': { fillColor: "#ff4d4d", color: "#b30000" }, 'Family Dispute': { fillColor: "#ffad33", color: "#cc7a00" },
        'Road Accident': { fillColor: "#800000", color: "#330000" }, 'Fire Accident': { fillColor: "#ff8000", color: "#b35900" },
        'Woman & Child Related': { fillColor: "#ff66cc", color: "#990066" }, 'Theft / Robbery': { fillColor: "#4d4d4d", color: "#000000" },
        'Prohibition Related': { fillColor: "#bf80ff", color: "#5900b3" }, 'default': { fillColor: "#808080", color: "#404040" }
    };
    function getStyleForCrime(crimeType) { const style = crimeStyles[crimeType] || crimeStyles['default']; return { ...style, radius: 6, weight: 1, opacity: 1, fillOpacity: 0.8 }; }

    let allData = [], pointLayerGroup = L.layerGroup().addTo(map), heatLayer = null, clusterLayerGroup = null, subdivisionSelect = null, subdivisionBoundaries = {};
    const heatmapOptionsDiv = document.getElementById('heatmap-options'), heatmapRadiusSlider = document.getElementById('heatmap-radius'), radiusValueSpan = document.getElementById('radius-value');

    initializeApp();

    async function initializeApp() {
        try {
            const [filterOptions, crimeData, analyticsData] = await Promise.all([ fetch('/api/filters').then(res => res.json()), fetch('/api/data').then(res => res.json()), fetch('/api/analytics').then(res => res.json()) ]);
            allData = crimeData;
            await loadAllBoundaries();
            populateCrimeTypeButtons(filterOptions.event_types);
            initializeSubdivisionDropdown(filterOptions.subdivisions);
            populateSubdivisionList(filterOptions.subdivisions);
            displayAnalytics(analyticsData);
            setupEventListeners();
            updateMap();
        } catch (error) { console.error("Failed to initialize application:", error); alert("Could not load initial data."); }
    }

    async function loadAllBoundaries() {
        map.createPane('boundaries'); map.getPane('boundaries').style.zIndex = 350;

        // --- NEW: Definitive mapping from filename to the official Subdivision name ---
        const FILENAME_TO_SUBDIVISION_MAP = {
            'kovilpatti.geojson': 'Kovilpatti',
            'Maniyachi.geojson': 'Maniyachi',
            'sathankulam.geojson': 'Sathankulam',
            'srivaikundam.geojson': 'Srivaikundam',
            'thiruchendur.geojson': 'Tiruchendur',
            'Thoothukudi Rural.geojson': 'Thoothukudi Rural',
            'Thoothukudi Town.geojson': 'Thoothukudi Town',
            'vilathikulam.geojson': 'Vilathikulam'
        };

        const boundaryFiles = Object.keys(FILENAME_TO_SUBDIVISION_MAP);
        const districtOutlineFile = 'THOOTHUKUDI POLICE MAP OUTLINE.geojson';
        const subDivisionStyle = { fill: false, weight: 1.5, opacity: 0.8, color: '#333333', dashArray: '5, 5' };
        const districtOutlineStyle = { fill: false, weight: 3, opacity: 0.9, color: '#005A9C' };

        function onEachFeature(feature, layer, subdivisionName) {
            subdivisionBoundaries[subdivisionName] = layer;
            layer.bindTooltip(subdivisionName, { permanent: false, direction: 'center', className: 'boundary-tooltip' });
            layer.on({
                mouseover: (e) => e.target.setStyle({ weight: 3, color: '#FFC107', opacity: 1 }),
                mouseout: (e) => e.target.setStyle(subDivisionStyle),
                click: (e) => {
                    map.fitBounds(e.target.getBounds());
                    if (subdivisionSelect) {
                        // This will now use the guaranteed correct name from our map
                        subdivisionSelect.setSelected(subdivisionName);
                    }
                }
            });
        }
        
        for (const fileName of boundaryFiles) {
            try {
                // Get the guaranteed correct subdivision name from our map
                const subdivisionName = FILENAME_TO_SUBDIVISION_MAP[fileName];
                if (!subdivisionName) continue; // Skip if a file is not in our map

                const response = await fetch(`/static/geojson/${fileName}`);
                const geojsonData = await response.json();
                L.geoJSON(geojsonData, { 
                    style: subDivisionStyle, 
                    onEachFeature: (f, l) => onEachFeature(f, l, subdivisionName), 
                    pane: 'boundaries' 
                }).addTo(map);
            } catch (error) { console.warn(`Could not load boundary: ${fileName}`, error); }
        }
        
        try {
            const response = await fetch(`/static/geojson/${districtOutlineFile}`);
            const geojsonData = await response.json();
            L.geoJSON(geojsonData, { style: districtOutlineStyle, pane: 'boundaries' }).addTo(map);
        } catch (error) { console.warn(`Could not load district outline: ${districtOutlineFile}`, error); }
    }

    function initializeSubdivisionDropdown(subdivisions) {
        const selectElement = document.getElementById('subdivision-select');
        selectElement.innerHTML = subdivisions.map(subdiv => `<option value="${subdiv}">${subdiv}</option>`).join('');
        subdivisionSelect = new SlimSelect({
            select: '#subdivision-select',
            settings: { placeholderText: 'Select Subdivisions', allowDeselect: true, closeOnSelect: false },
            events: { afterChange: (info) => { 
                updateMap();
                document.querySelectorAll('.subdivision-list-item').forEach(item => {
                    if (info.some(s => s.value === item.dataset.station)) item.classList.add('active');
                    else item.classList.remove('active');
                });
            }}
        });
        subdivisionSelect.setSelected(subdivisions);
    }
    
    function populateSubdivisionList(subdivisions) {
        const container = document.getElementById('subdivision-list-container');
        container.innerHTML = subdivisions.map(subdiv => `<div class="subdivision-list-item" data-station="${subdiv}">${subdiv}</div>`).join('');
        container.addEventListener('click', (e) => {
            if (e.target.classList.contains('subdivision-list-item')) {
                const subdivName = e.target.dataset.station;
                subdivisionSelect.setSelected(subdivName);
                if (subdivisionBoundaries[subdivName]) { map.fitBounds(subdivisionBoundaries[subdivName].getBounds()); }
                document.querySelectorAll('.subdivision-list-item.active').forEach(item => item.classList.remove('active'));
                e.target.classList.add('active');
            }
        });
    }

    function populateCrimeTypeButtons(eventTypes) {
        const container = document.getElementById('crime-buttons-container');
        let buttonsHTML = '<button class="filter-btn active" data-crime="All">All</button>';
        eventTypes.forEach(type => { buttonsHTML += `<button class="filter-btn" data-crime="${type}">${type}</button>`; });
        container.innerHTML = buttonsHTML;
    }

    function displayAnalytics(analytics) {
        const container = document.getElementById('analytics-container');
        let analyticsHTML = `<p><strong>Total Cases:</strong> ${analytics.total_cases}</p>`;
        if (analytics.top_stations && analytics.top_stations.length > 0) {
            analyticsHTML += `<strong>Top Police Stations:</strong><ul>`;
            analytics.top_stations.forEach(([station, count]) => { analyticsHTML += `<li>${station}: ${count} cases</li>`; });
            analyticsHTML += `</ul>`;
        }
        container.innerHTML = analyticsHTML;
    }

    function setupEventListeners() {
        document.getElementById('crime-buttons-container').addEventListener('click', (e) => {
            if (e.target.classList.contains('filter-btn')) { document.querySelector('.filter-btn.active').classList.remove('active'); e.target.classList.add('active'); updateMap(); }
        });
        document.querySelectorAll('.area-filter, input[name="mapView"]').forEach(el => el.addEventListener('change', updateMap));
        document.getElementById('fromDate').addEventListener('change', updateMap);
        document.getElementById('toDate').addEventListener('change', updateMap);
        document.querySelectorAll('input[name="mapView"]').forEach(radio => radio.addEventListener('change', () => { heatmapOptionsDiv.style.display = radio.value === 'heat' ? 'block' : 'none'; updateMap(); }));
        heatmapRadiusSlider.addEventListener('input', (e) => {
            radiusValueSpan.textContent = e.target.value;
            if (heatLayer) { heatLayer.setOptions({ radius: e.target.value, blur: e.target.value / 2 }); }
        });
        document.getElementById('resetFilters').addEventListener('click', () => {
            document.querySelector('.filter-btn.active').classList.remove('active'); document.querySelector('.filter-btn[data-crime="All"]').classList.add('active');
            document.getElementById('fromDate').value = ''; document.getElementById('toDate').value = '';
            document.querySelectorAll('.area-filter').forEach(cb => cb.checked = true);
            const allStationValues = Array.from(document.getElementById('subdivision-select').options).map(opt => opt.value);
            subdivisionSelect.setSelected(allStationValues);
            document.querySelectorAll('.subdivision-list-item.active').forEach(item => item.classList.remove('active'));
            document.querySelector('input[name="mapView"][value="point"]').checked = true;
            heatmapRadiusSlider.value = 25; radiusValueSpan.textContent = 25; heatmapOptionsDiv.style.display = 'none';
            map.setView([8.78, 78.13], 10);
        });
    }

    function applyFilters() {
        const activeCrime = document.querySelector('.filter-btn.active').dataset.crime;
        const fromDateStr = document.getElementById('fromDate').value, toDateStr = document.getElementById('toDate').value;
        const selectedAreas = Array.from(document.querySelectorAll('.area-filter:checked')).map(cb => cb.value);
        const selectedSubdivisions = subdivisionSelect.getSelected();
        return allData.filter(item => {
            if (activeCrime !== 'All' && item['Event Type'] !== activeCrime) return false;
            if (selectedAreas.length > 0 && !selectedAreas.includes(item.Category)) return false;
            if (selectedSubdivisions.length > 0 && !selectedSubdivisions.includes(item.Subdivision)) return false;
            if (fromDateStr && item.Date < fromDateStr) return false;
            if (toDateStr && item.Date > toDateStr) return false;
            return true;
        });
    }

    function updateMap() {
        const filteredData = applyFilters();
        const mapView = document.querySelector('input[name="mapView"]:checked').value;
        clearAllLayers();
        heatmapOptionsDiv.style.display = mapView === 'heat' ? 'block' : 'none';
        if (mapView === 'point') drawPointMap(filteredData);
        else if (mapView === 'cluster') drawClusterMap(filteredData);
        else if (mapView === 'heat') drawHeatMap(filteredData);
    }
    
    function clearAllLayers() { pointLayerGroup.clearLayers(); if (heatLayer) map.removeLayer(heatLayer); if (clusterLayerGroup) map.removeLayer(clusterLayerGroup); heatLayer = null; clusterLayerGroup = null; }
    
    function createPopupContent(item) { return `<strong>Event:</strong> ${item['Event Type'] || 'N/A'}<br><strong>Subdivision:</strong> ${item.Subdivision || 'N/A'}<br><strong>Police Station:</strong> ${item['Police Station'] || 'N/A'}<br><strong>Complaint:</strong> ${item.Complaint || 'N/A'}<br><strong>Date:</strong> ${item.Date || 'N/A'}`; }

    function drawPointMap(data) { const canvasRenderer = L.canvas(); data.forEach(item => { const style = getStyleForCrime(item['Event Type']); L.circleMarker([item.Latitude, item.Longitude], { ...style, renderer: canvasRenderer }).bindPopup(createPopupContent(item)).addTo(pointLayerGroup); }); }
    
    function drawClusterMap(data) {
        clusterLayerGroup = L.markerClusterGroup();
        data.forEach(item => { const style = getStyleForCrime(item['Event Type']); const marker = L.circleMarker([item.Latitude, item.Longitude], style).bindPopup(createPopupContent(item)); clusterLayerGroup.addLayer(marker); });
        map.addLayer(clusterLayerGroup);
    }
    
    function drawHeatMap(data) {
        if (data.length === 0) return;
        const currentRadius = heatmapRadiusSlider.value;
        const heatPoints = data.map(item => [item.Latitude, item.Longitude, 0.5]);
        heatLayer = L.heatLayer(heatPoints, { radius: currentRadius, blur: currentRadius / 2, maxZoom: 18 }).addTo(map);
    }
});