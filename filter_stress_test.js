import http from 'k6/http';
import { check, sleep } from 'k6';

// Poisson distribution implementation
function poisson(mean) {
    const L = Math.exp(-mean);
    let p = 1.0;
    let k = 0;
    
    do {
        k++;
        p *= Math.random();
    } while (p > L);
    
    return k - 1;
}

// Helper function to generate date strings
function getDateString(daysAgo) {
    const date = new Date();
    date.setDate(date.getDate() - daysAgo);
    return date.toISOString().split('T')[0];
}

export const options = {
    stages: [
        { duration: '2m', target: 30 },    // Ramp up to 30 users
        { duration: '3m', target: 30 },    // Stay at 30 users
        { duration: '2m', target: 60 },    // Ramp up to 60 users
        { duration: '3m', target: 60 },    // Stay at 60 users
        { duration: '2m', target: 100 },   // Ramp up to 100 users
        { duration: '3m', target: 100 },   // Stay at 100 users
        { duration: '2m', target: 150 },   // Ramp up to 150 users
        { duration: '3m', target: 150 },   // Stay at 150 users
        { duration: '2m', target: 0 },     // Ramp down to 0 users
    ],
    thresholds: {
        http_req_duration: ['p(95)<10000'], // 95% of requests should be below 10s
        http_req_failed: ['rate<0.3'],      // Less than 30% of requests should fail
    },
};

const API_KEY = __ENV.SECRET_API_KEY;
const BASE_URL = 'http://localhost:8000';

// Base data for filters
const locations = ["Jakarta", "Bandung", "Surabaya", "Medan", "Bali", "Yogyakarta"];
const diseases = ["COVID-19", "DBD", "Malaria", "Flu", "Tuberculosis"];
const portals = ["kompas.com", "detik.com", "tribunnews.com", "cnnindonesia.com"];

// Test payloads with clear patterns
const payloads = [
    // Pattern 1: Location-based queries
    {
        name: "location_single",
        data: { 
            locations: [locations[0]]
        }
    },
    {
        name: "location_multiple",
        data: { 
            locations: locations.slice(0, 3)
        }
    },

    // Pattern 2: Disease-based queries
    {
        name: "disease_single",
        data: { 
            diseases: [diseases[0]]
        }
    },
    {
        name: "disease_multiple",
        data: { 
            diseases: diseases.slice(0, 3)
        }
    },

    // Pattern 3: Combined filters with date ranges
    {
        name: "combined_recent",
        data: {
            diseases: [diseases[0], diseases[1]],
            locations: [locations[0], locations[1]],
            level_of_alertness: 3,
            portals: [portals[0], portals[1]],
            start_date: getDateString(7),  // Last 7 days
            end_date: getDateString(0)     // Today
        }
    },
    {
        name: "combined_monthly",
        data: {
            diseases: [diseases[2], diseases[3]],
            locations: [locations[2], locations[3]],
            level_of_alertness: 2,
            portals: [portals[2]],
            start_date: getDateString(30),  // Last 30 days
            end_date: getDateString(0)      // Today
        }
    },
    {
        name: "combined_quarterly",
        data: {
            diseases: [diseases[0], diseases[4]],
            locations: [locations[4], locations[5]],
            level_of_alertness: 1,
            portals: portals,
            start_date: getDateString(90),  // Last 90 days
            end_date: getDateString(0)      // Today
        }
    }
];

export default function () {
    const headers = {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
    };

    // Randomly select a payload
    const payload = payloads[Math.floor(Math.random() * payloads.length)];

    const response = http.post(
        `${BASE_URL}/cases/locations/`,
        JSON.stringify(payload.data),
        { 
            headers,
            timeout: '30s'
        }
    );

    // Validate response structure
    check(response, {
        'status is 200': (r) => r.status === 200,
        'response time < 10s': (r) => r.timings.duration < 10000,
        'has valid response': (r) => {
            if (r.status !== 200) return false;
            try {
                const json = r.json();
                return Array.isArray(json) && json.every(item => 
                    'id' in item && 
                    'location__longitude' in item && 
                    'location__latitude' in item && 
                    'city' in item && 
                    'location__province' in item
                );
            } catch (e) {
                return false;
            }
        }
    });

    // Use Poisson distribution for sleep time
    const sleepTime = poisson(0.5) / 2;
    sleep(sleepTime);
} 