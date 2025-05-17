import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';
import exec from 'k6/execution';
import crypto from 'k6/crypto';

// Helper function for secure random
function secureRandom() {
    return crypto.randomBytes(4).readUInt32LE(0) / 0xffffffff;
}

// Poisson distribution implementation
function poisson(mean) {
    const L = Math.exp(-mean);
    let p = 1.0;
    let k = 0;
    
    do {
        k++;
        p *= secureRandom();  // Use secure random instead of Math.random()
    } while (p > L);
    
    return k - 1;
}

// Define custom metrics
const errorRate = new Rate('errors');

// Test configuration
const API_KEY = __ENV.SECRET_API_KEY || '-I60gpBOcqRcylybyWYFCeo7dlXb8DQSOtnGtUauokg';
const BASE_URL = 'http://localhost:8000'
const ENDPOINT = '/api/diseases/severity-stats/';

// Define stress test scenario
export const options = {
  scenarios: {
    stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 75 },   
        { duration: '5m', target: 100 },   
        { duration: '5m', target: 125 },
        { duration: '5m', target: 200 },
        { duration: '5m', target: 250 },
        { duration: '5m', target: 250 },
        { duration: '10m', target: 0 },     
      ],
      gracefulRampDown: '10s',
    }
  },
  thresholds: {
    http_req_duration: ['p(95)<2000'], // 95% of requests should be below 2s
    http_req_failed: ['rate<0.1'],     // Less than 10% of requests should fail
    errors: ['rate<0.1'],              // Custom error metric
  },
  systemTags: ['scenario', 'status', 'method'],
};

export default function () {
  const headers = {
    'X-API-Key': API_KEY,
  };

  // Send the request
  const response = http.get(`${BASE_URL}${ENDPOINT}`, { headers });
  
  // Check response
  const success = check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 2s': (r) => r.timings.duration < 2000,
    'has valid response': (r) => {
      try {
        const body = r.json();
        return body.data && Array.isArray(body.data) && body.data.length > 0;
      } catch (e) {
        console.error('Error parsing JSON:', e.message);
        return false;
      }
    },
    'has expected structure': (r) => {
      try {
        const body = r.json();
        if (!body.data || !Array.isArray(body.data)) return false;
        
        return body.data.every(item => 
          item.name && 
          item.severity_counts && 
          typeof item.severity_counts.hospitalisasi === 'number' &&
          typeof item.severity_counts.insiden === 'number' &&
          typeof item.severity_counts.mortalitas === 'number' &&
          typeof item.total_cases === 'number'
        );
      } catch (e) {
        console.error('Error checking structure:', e.message);
        return false;
      }
    },
  });
  
  // Update custom error rate metric
  errorRate.add(!success);
  
  // Log current stage info
  if (__ENV.DEBUG) {
    console.log(`VUs: ${exec.instance.vusActive}, Iteration: ${exec.instance.iterationInInstance}`);
  }
  
  // Use shorter sleep times for stress test (1 second mean)
  const sleepTime = poisson(1) / 2;
  sleep(sleepTime);
}