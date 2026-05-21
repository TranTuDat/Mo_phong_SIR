#!/usr/bin/env python
"""
Test script for SIR Simulation API
Kiểm tra các API endpoints mới cho SIR Simulation
"""

import requests
import json
import time

BASE_URL = 'http://localhost:5000'

def test_simulation_page():
    """Test redirect /simulation -> trang một giao diện"""
    print("Test 1: Loading /simulation (redirect)...")
    try:
        resp = requests.get(f'{BASE_URL}/simulation', allow_redirects=True)
        assert resp.status_code == 200
        assert 'simulation-container' in resp.text or 'view=sim' in resp.url
        print("✓ Trang SIR (gộp) tải được")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

def test_pure_sir_api():
    """Test Pure SIR API"""
    print("\nTest 2: Testing Pure SIR API...")
    try:
        payload = {
            'model': 'pure',
            'transmission_rate': 0.3,
            'recovery_rate': 0.1,
            'days': 50,
            'seed': 42
        }
        resp = requests.post(f'{BASE_URL}/api/simulate-sir', json=payload)
        
        assert resp.status_code == 200, f"Status code: {resp.status_code}"
        data = resp.json()
        
        assert 'model' in data
        assert data['model'] == 'pure'
        assert 'peak_day' in data
        assert 'peak_infected' in data
        assert 'final_day' in data
        assert 'history' in data
        
        print(f"✓ Pure SIR simulation successful")
        print(f"  - Peak day: {data['peak_day']}")
        print(f"  - Peak infected: {data['peak_infected']}")
        print(f"  - Final day: {data['final_day']}")
        print(f"  - History points: {len(data['history'])}")
        
        return True
    except Exception as e:
        print(f"✗ Pure SIR API test failed: {e}")
        return False

def test_dynamic_sir_api():
    """Test Dynamic SIR API"""
    print("\nTest 3: Testing Dynamic SIR API...")
    try:
        payload = {
            'model': 'dynamic',
            'transmission_rate': 0.3,
            'recovery_rate': 0.1,
            'days': 50,
            'top_k': 10,
            'seed': 42
        }
        resp = requests.post(f'{BASE_URL}/api/simulate-sir', json=payload)
        
        assert resp.status_code == 200, f"Status code: {resp.status_code}"
        data = resp.json()
        
        assert 'model' in data
        assert data['model'] == 'dynamic'
        assert 'peak_day' in data
        assert 'peak_infected' in data
        assert 'final_day' in data
        assert 'history' in data
        assert 'top_k' in data
        assert data.get('intervention_day', 1) == 1
        
        print(f"✓ Dynamic SIR simulation successful")
        print(f"  - Peak day: {data['peak_day']}")
        print(f"  - Peak infected: {data['peak_infected']}")
        print(f"  - Final day: {data['final_day']}")
        print(f"  - Top-k: {data['top_k']}")
        print(f"  - History points: {len(data['history'])}")
        
        return True
    except Exception as e:
        print(f"✗ Dynamic SIR API test failed: {e}")
        return False

def test_dynamic_sir_intervention_day():
    """Dynamic SIR với ngày can thiệp > 1"""
    print("\nTest 3b: Dynamic SIR with intervention_day…")
    try:
        payload = {
            'model': 'dynamic',
            'transmission_rate': 0.3,
            'recovery_rate': 0.1,
            'days': 80,
            'top_k': 5,
            'seed': 42,
            'intervention_day': 20,
            'strategy': 'degree',
        }
        resp = requests.post(f'{BASE_URL}/api/simulate-sir', json=payload)
        assert resp.status_code == 200, f"Status code: {resp.status_code}"
        data = resp.json()
        assert data['model'] == 'dynamic'
        assert data['intervention_day'] == 20
        assert 'history' in data
        print(f"✓ intervention_day=20 OK, peak_infected={data['peak_infected']}")
        return True
    except Exception as e:
        print(f"✗ intervention_day test failed: {e}")
        return False

def test_comparison():
    """Test comparing two simulations"""
    print("\nTest 4: Testing comparison between Pure and Dynamic SIR...")
    try:
        pure_payload = {
            'model': 'pure',
            'transmission_rate': 0.3,
            'recovery_rate': 0.1,
            'days': 50,
            'seed': 42
        }
        
        dynamic_payload = {
            'model': 'dynamic',
            'transmission_rate': 0.3,
            'recovery_rate': 0.1,
            'days': 50,
            'top_k': 10,
            'seed': 42
        }
        
        resp1 = requests.post(f'{BASE_URL}/api/simulate-sir', json=pure_payload)
        resp2 = requests.post(f'{BASE_URL}/api/simulate-sir', json=dynamic_payload)
        
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        
        pure_data = resp1.json()
        dynamic_data = resp2.json()
        
        print(f"✓ Comparison test successful")
        print(f"  Pure SIR peak infected: {pure_data['peak_infected']}")
        print(f"  Dynamic SIR peak infected: {dynamic_data['peak_infected']}")
        reduction = (pure_data['peak_infected'] - dynamic_data['peak_infected']) / pure_data['peak_infected'] * 100
        print(f"  Reduction: {reduction:.1f}%")
        
        return True
    except Exception as e:
        print(f"✗ Comparison test failed: {e}")
        return False

if __name__ == '__main__':
    print("="*60)
    print("SIR Simulation API Tests")
    print("="*60)
    print("\nMake sure the Flask app is running on port 5000")
    print("Run: python app.py")
    print("="*60)
    
    time.sleep(2)  # Give user time to read
    
    results = []
    results.append(test_simulation_page())
    results.append(test_pure_sir_api())
    results.append(test_dynamic_sir_api())
    results.append(test_dynamic_sir_intervention_day())
    results.append(test_comparison())
    
    print("\n" + "="*60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("="*60)
