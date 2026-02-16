// Greenhouse Dashboard Controller
const API_BASE = '';
let updateInterval = null;
let climateChart = null;
let soilChart = null;
let currentMode = 'manual';
let currentLightMode = 'manual';

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard loading...');
    initDashboard();
    setupEventListeners();
    startDataUpdates();
    console.log('Dashboard loaded');
});

function initDashboard() {
    // Initialize charts if elements exist
    const climateChart = document.getElementById('climateChart');
    const soilChart = document.getElementById('soilChart');
    const historyChart = document.getElementById('historyChart');
    
    if (climateChart) initClimateChart();
    if (soilChart) initSoilChart();
    
    // Load initial data
    updateSensorData();
    updateRelayStates();
    updateStatus();
    loadSettings();
}

function setupEventListeners() {
    // Check if elements exist before adding listeners
    const manualModeBtn = document.getElementById('manualModeBtn');
    const autoModeBtn = document.getElementById('autoModeBtn');
    const lightManualBtn = document.getElementById('lightManualBtn');
    const lightScheduleBtn = document.getElementById('lightScheduleBtn');
    
    if (manualModeBtn) {
        manualModeBtn.addEventListener('click', () => setClimateMode('manual'));
    }
    
    if (autoModeBtn) {
        autoModeBtn.addEventListener('click', () => setClimateMode('auto'));
    }
    
    if (lightManualBtn) {
        lightManualBtn.addEventListener('click', () => setLightMode('manual'));
    }
    
    if (lightScheduleBtn) {
        lightScheduleBtn.addEventListener('click', () => setLightMode('schedule'));
    }
    
    // Relay toggles
    const humidifierToggle = document.getElementById('humidifierToggle');
    const dehumidifierToggle = document.getElementById('dehumidifierToggle');
    const heaterToggle = document.getElementById('heaterToggle');
    const lightToggle = document.getElementById('lightToggle');
    
    if (humidifierToggle) {
        humidifierToggle.addEventListener('change', (e) => controlRelay('humidifier', e.target.checked));
    }
    if (dehumidifierToggle) {
        dehumidifierToggle.addEventListener('change', (e) => controlRelay('dehumidifier', e.target.checked));
    }
    if (heaterToggle) {
        heaterToggle.addEventListener('change', (e) => controlRelay('heater', e.target.checked));
    }
    if (lightToggle) {
        lightToggle.addEventListener('change', (e) => controlRelay('light', e.target.checked));
    }
    
    // Settings save button
    const saveSettingsBtn = document.getElementById('saveSettingsBtn');
    if (saveSettingsBtn) {
        saveSettingsBtn.addEventListener('click', saveClimateSettings);
    }
    
    // Light schedule save button
    const saveLightScheduleBtn = document.getElementById('saveLightScheduleBtn');
    if (saveLightScheduleBtn) {
        saveLightScheduleBtn.addEventListener('click', saveLightSchedule);
    }
    
    // Time range selector
    const timeRange = document.getElementById('timeRange');
    if (timeRange) {
        timeRange.addEventListener('change', (e) => {
            updateCharts(parseInt(e.target.value));
        });
    }
}

function startDataUpdates() {
    // Update sensor data every 5 seconds
    updateInterval = setInterval(() => {
        updateSensorData();
        updateRelayStates();
        updateStatus();
    }, 5000);
    
    // Update charts every 30 seconds
    setInterval(() => {
        const hours = parseInt(document.getElementById('timeRange').value);
        updateCharts(hours);
    }, 30000);
}

// ========== API CALLS ==========

async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(API_BASE + endpoint, options);
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        updateConnectionStatus(false);
        return null;
    }
}

// ========== DATA UPDATES ==========

async function updateSensorData() {
    console.log('Fetching sensor data...');
    const data = await apiCall('/api/sensors/current');
    console.log('Sensor data received:', data);
    
    if (data && !data.error) {
        updateConnectionStatus(true);
        
        // Update temperature (convert to Fahrenheit)
        const tempF = data.temperature ? (data.temperature * 9/5 + 32).toFixed(1) : '--';
        const tempC = data.temperature ? data.temperature.toFixed(1) : '--';
        console.log('Setting tempValue to:', tempF);
        document.getElementById('tempValue').textContent = tempF;
        const tempCelsius = document.getElementById('tempCelsius');
        if (tempCelsius) {
            tempCelsius.textContent = tempC + '°C';
        }
        
        // Update humidity
        console.log('Setting humidityValue to:', data.humidity ? data.humidity.toFixed(0) : '--');
        document.getElementById('humidityValue').textContent = 
            data.humidity ? data.humidity.toFixed(0) : '--';
        
        // Update soil moisture
        if (data.soil_moisture) {
            const soil1 = document.getElementById('soil1Value');
            const soil2 = document.getElementById('soil2Value');
            const soil3 = document.getElementById('soil3Value');
            const soil4 = document.getElementById('soil4Value');
            
            if (soil1) soil1.textContent = data.soil_moisture.soil1 ? data.soil_moisture.soil1.toFixed(1) : '--';
            if (soil2) soil2.textContent = data.soil_moisture.soil2 ? data.soil_moisture.soil2.toFixed(1) : '--';
            if (soil3) soil3.textContent = data.soil_moisture.soil3 ? data.soil_moisture.soil3.toFixed(1) : '--';
            if (soil4) soil4.textContent = data.soil_moisture.soil4 ? data.soil_moisture.soil4.toFixed(1) : '--';
        }
        
        // Update target displays
        const settings = await apiCall('/api/climate/settings');
        if (settings && !settings.error) {
            const targetHumidityDisplay = document.getElementById('targetHumidityDisplay');
            const targetTempDisplay = document.getElementById('targetTempDisplay');
            if (targetHumidityDisplay) {
                targetHumidityDisplay.textContent = settings.target_humidity ? settings.target_humidity + '%' : '--%';
            }
            if (targetTempDisplay) {
                const targetTempF = settings.target_temp ? (settings.target_temp * 9/5 + 32).toFixed(0) : '--';
                targetTempDisplay.textContent = targetTempF + '°F';
            }
        }
    } else {
        updateConnectionStatus(false);
    }
}

async function updateRelayStates() {
    const data = await apiCall('/api/relays');
    
    if (data && !data.error) {
        // Update toggle states without triggering change events
        setToggleState('humidifierToggle', data.humidifier);
        setToggleState('dehumidifierToggle', data.dehumidifier);
        setToggleState('heaterToggle', data.heater);
        setToggleState('lightToggle', data.light);
    }
}

async function updateStatus() {
    const data = await apiCall('/api/status');
    
    if (data && data.status === 'ok') {
        document.getElementById('board1Status').textContent = 
            data.board1_connected ? '✓ Connected' : '✗ Disconnected';
        
        if (data.last_sensor_update > 0) {
            const seconds = Math.floor(Date.now() / 1000 - data.last_sensor_update);
            document.getElementById('lastUpdate').textContent = 
                seconds < 60 ? `${seconds}s ago` : `${Math.floor(seconds / 60)}m ago`;
        }
        
        if (data.climate_controller) {
            document.getElementById('climateModeStatus').textContent = 
                data.climate_controller.enabled ? 'Auto' : 'Manual';
        }
        
        if (data.light_scheduler) {
            document.getElementById('lightModeStatus').textContent = 
                data.light_scheduler.enabled ? 'Schedule' : 'Manual';
        }
    }
}

async function loadSettings() {
    // Load climate settings
    const climateData = await apiCall('/api/climate/settings');
    if (climateData && !climateData.error) {
        document.getElementById('targetTemp').value = climateData.target_temp || 22;
        document.getElementById('tempTolerance').value = climateData.temp_tolerance || 1;
        document.getElementById('targetHumidity').value = climateData.target_humidity || 60;
        document.getElementById('humidityTolerance').value = climateData.humidity_tolerance || 5;
    }
    
    // Load light schedule
    const lightData = await apiCall('/api/light/schedule');
    if (lightData && !lightData.error) {
        document.getElementById('lightOnTime').value = lightData.on_time || '06:00';
        document.getElementById('lightOffTime').value = lightData.off_time || '22:00';
    }
    
    // Load modes
    const climateMode = await apiCall('/api/climate/mode');
    if (climateMode) {
        setClimateModeUI(climateMode.mode || 'manual');
    }
    
    const lightMode = await apiCall('/api/light/mode');
    if (lightMode) {
        setLightModeUI(lightMode.mode || 'manual');
    }
}

// ========== CONTROL FUNCTIONS ==========

async function controlRelay(relayName, state) {
    const result = await apiCall(`/api/relays/${relayName}`, 'POST', { state: state });
    
    if (result && result.error) {
        alert(result.message || result.error);
        // Revert toggle
        updateRelayStates();
    }
}

async function setClimateMode(mode) {
    const result = await apiCall('/api/climate/mode', 'POST', { mode: mode });
    
    if (result && result.success) {
        setClimateModeUI(mode);
    }
}

async function setLightMode(mode) {
    const result = await apiCall('/api/light/mode', 'POST', { mode: mode });
    
    if (result && result.success) {
        setLightModeUI(mode);
    }
}

async function saveClimateSettings() {
    const settings = {
        target_temp: parseFloat(document.getElementById('targetTemp').value),
        temp_tolerance: parseFloat(document.getElementById('tempTolerance').value),
        target_humidity: parseFloat(document.getElementById('targetHumidity').value),
        humidity_tolerance: parseFloat(document.getElementById('humidityTolerance').value)
    };
    
    const result = await apiCall('/api/climate/settings', 'POST', settings);
    
    if (result && result.success) {
        showNotification('Settings saved successfully', 'success');
    } else {
        showNotification('Failed to save settings', 'error');
    }
}

async function saveLightSchedule() {
    const schedule = {
        on_time: document.getElementById('lightOnTime').value,
        off_time: document.getElementById('lightOffTime').value,
        enabled: true
    };
    
    const result = await apiCall('/api/light/schedule', 'POST', schedule);
    
    if (result && result.success) {
        showNotification('Light schedule saved', 'success');
    } else {
        showNotification('Failed to save schedule', 'error');
    }
}

// ========== UI HELPERS ==========

function setToggleState(id, state) {
    const toggle = document.getElementById(id);
    if (toggle && toggle.checked !== state) {
        toggle.checked = state;
    }
}

function setClimateModeUI(mode) {
    currentMode = mode;
    
    if (mode === 'auto') {
        document.getElementById('manualModeBtn').classList.remove('active');
        document.getElementById('autoModeBtn').classList.add('active');
        document.getElementById('manualControls').classList.add('hidden');
        document.getElementById('autoControls').classList.remove('hidden');
    } else {
        document.getElementById('manualModeBtn').classList.add('active');
        document.getElementById('autoModeBtn').classList.remove('active');
        document.getElementById('manualControls').classList.remove('hidden');
        document.getElementById('autoControls').classList.add('hidden');
    }
}

function setLightModeUI(mode) {
    currentLightMode = mode;
    
    if (mode === 'schedule') {
        document.getElementById('lightManualBtn').classList.remove('active');
        document.getElementById('lightScheduleBtn').classList.add('active');
        document.getElementById('lightManualControl').classList.add('hidden');
        document.getElementById('lightScheduleControl').classList.remove('hidden');
    } else {
        document.getElementById('lightManualBtn').classList.add('active');
        document.getElementById('lightScheduleBtn').classList.remove('active');
        document.getElementById('lightManualControl').classList.remove('hidden');
        document.getElementById('lightScheduleControl').classList.add('hidden');
    }
}

function updateConnectionStatus(connected) {
    const indicator = document.getElementById('connectionStatus');
    const text = document.getElementById('connectionText');
    
    if (connected) {
        indicator.classList.remove('offline');
        indicator.classList.add('online');
        text.textContent = 'Connected';
    } else {
        indicator.classList.remove('online');
        indicator.classList.add('offline');
        text.textContent = 'Disconnected';
    }
}

function showNotification(message, type = 'info') {
    // Simple notification (could be replaced with a better notification system)
    alert(message);
}

// ========== CHARTS ==========

function initClimateChart() {
    const ctx = document.getElementById('climateChart').getContext('2d');
    
    climateChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Temperature (°C)',
                    data: [],
                    borderColor: '#f44336',
                    backgroundColor: 'rgba(244, 67, 54, 0.1)',
                    yAxisID: 'y',
                    tension: 0.4,
                    cubicInterpolationMode: 'monotone',
                    pointRadius: 0,
                },
                {
                    label: 'Humidity (%)',
                    data: [],
                    borderColor: '#2196F3',
                    backgroundColor: 'rgba(33, 150, 243, 0.1)',
                    yAxisID: 'y1',
                    tension: 0.4,
                    cubicInterpolationMode: 'monotone',
                    pointRadius: 0,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: '#999'
                    }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Temperature (°C)',
                        color: '#f44336'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: '#f44336'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Humidity (%)',
                        color: '#2196F3'
                    },
                    grid: {
                        drawOnChartArea: false,
                    },
                    ticks: {
                        color: '#2196F3'
                    }
                }
            },
            plugins: {
                legend: {
                    labels: {
                        color: '#e0e0e0'
                    }
                }
            }
        }
    });
}

function initSoilChart() {
    const ctx = document.getElementById('soilChart').getContext('2d');
    
    soilChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Sensor 1',
                    data: [],
                    borderColor: '#4CAF50',
                    backgroundColor: 'rgba(76, 175, 80, 0.1)',
                },
                {
                    label: 'Sensor 2',
                    data: [],
                    borderColor: '#8BC34A',
                    backgroundColor: 'rgba(139, 195, 74, 0.1)',
                },
                {
                    label: 'Sensor 3',
                    data: [],
                    borderColor: '#CDDC39',
                    backgroundColor: 'rgba(205, 220, 57, 0.1)',
                },
                {
                    label: 'Sensor 4',
                    data: [],
                    borderColor: '#FFC107',
                    backgroundColor: 'rgba(255, 193, 7, 0.1)',
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: '#999'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Soil Moisture (%)',
                        color: '#4CAF50'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: '#4CAF50'
                    }
                }
            },
            plugins: {
                legend: {
                    labels: {
                        color: '#e0e0e0'
                    }
                }
            }
        }
    });
}

async function updateCharts(hours = 24) {
    const data = await apiCall(`/api/sensors/history?hours=${hours}`);
    
    if (data && Array.isArray(data)) {
        // Prepare data
        const labels = [];
        const tempData = [];
        const humidityData = [];
        const soil1Data = [];
        const soil2Data = [];
        const soil3Data = [];
        const soil4Data = [];
        
        data.forEach(reading => {
            const date = new Date(reading.timestamp * 1000);
            labels.push(date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
            tempData.push(reading.temperature);
            humidityData.push(reading.humidity);
            soil1Data.push(reading.soil1);
            soil2Data.push(reading.soil2);
            soil3Data.push(reading.soil3);
            soil4Data.push(reading.soil4);
        });
        
        // Update climate chart
        climateChart.data.labels = labels;
        climateChart.data.datasets[0].data = tempData;
        climateChart.data.datasets[1].data = humidityData;
        climateChart.update('none');
        
        // Update soil chart
        soilChart.data.labels = labels;
        soilChart.data.datasets[0].data = soil1Data;
        soilChart.data.datasets[1].data = soil2Data;
        soilChart.data.datasets[2].data = soil3Data;
        soilChart.data.datasets[3].data = soil4Data;
        soilChart.update('none');
    }
}

// Load crash log
async function loadCrashLog() {
    try {
        const response = await fetch(`${API_BASE}/api/system/crashes?limit=20`);
        const crashes = await response.json();
        
        const container = document.getElementById('crashLogContainer');
        
        if (crashes.length === 0) {
            container.innerHTML = '<div style="color: #4CAF50;">✓ No crashes detected - system healthy</div>';
            return;
        }
        
        let html = '';
        crashes.forEach(crash => {
            const date = new Date(crash.timestamp * 1000);
            const dateStr = date.toLocaleString();
            const type = crash.crash_type === 'critical_reboot' ? '🔴 REBOOT' : '⚠️ SHUTDOWN';
            html += `<div style="margin-bottom: 8px; padding: 8px; background: rgba(255,0,0,0.1); border-left: 3px solid #f44336; border-radius: 4px;">
                <div style="color: #f44336; font-weight: bold;">${type} - ${dateStr}</div>
                <div style="color: #ddd; margin-top: 4px;">${crash.description}</div>
            </div>`;
        });
        
        container.innerHTML = html;
    } catch (error) {
        console.error('Error loading crash log:', error);
        document.getElementById('crashLogContainer').innerHTML = '<div style="color: #f44336;">Error loading crash log</div>';
    }
}

// Load crash log on startup
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => loadCrashLog(), 1000);
});
