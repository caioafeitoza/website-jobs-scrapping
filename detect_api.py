#!/usr/bin/env python3
"""
Helper script to detect job board APIs and test endpoints.

Usage:
    python3 detect_api.py https://company.com/careers
    python3 detect_api.py https://api.company.com/jobs
"""

import requests
from bs4 import BeautifulSoup
import json
import sys


def find_api_endpoint(career_url):
    """Try to find the API endpoint for a career page"""
    
    print(f"\n🔍 Analyzing: {career_url}")
    print("=" * 70)
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(career_url, headers=headers, timeout=10)
        content = response.text.lower()
        
        # Check for known platforms
        platforms = {
            'Greenhouse': {
                'indicators': ['greenhouse.io', 'grnhse.io', 'gh_jid'],
                'color': '🟢'
            },
            'Lever': {
                'indicators': ['lever.co', 'lever-client', 'lever-job'],
                'color': '🔵'
            },
            'Ashby': {
                'indicators': ['ashbyhq.com', 'ashby-job'],
                'color': '🟣'
            },
            'Workday': {
                'indicators': ['myworkdayjobs.com', 'workday'],
                'color': '🟡'
            },
            'SmartRecruiters': {
                'indicators': ['smartrecruiters.com'],
                'color': '🟠'
            },
            'Jobvite': {
                'indicators': ['jobvite.com'],
                'color': '🔴'
            },
        }
        
        detected = None
        for platform, config in platforms.items():
            if any(indicator in content for indicator in config['indicators']):
                print(f"\n{config['color']} Detected platform: {platform}")
                detected = platform
                
                # Try to extract company name and build API URL
                api_url = None
                
                if platform == 'Greenhouse':
                    if 'boards.greenhouse.io' in career_url:
                        company = career_url.split('boards.greenhouse.io/')[-1].split('/')[0]
                        api_url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
                    elif 'greenhouse.io' in content:
                        # Try to find company name in page source
                        try:
                            soup = BeautifulSoup(response.text, 'html.parser')
                            scripts = soup.find_all('script')
                            for script in scripts:
                                if script.string and 'boards-api.greenhouse.io' in script.string:
                                    # Extract company name from API URL in script
                                    import re
                                    match = re.search(r'boards-api\.greenhouse\.io/v1/boards/([^/\'"]+)', script.string)
                                    if match:
                                        company = match.group(1)
                                        api_url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
                                        break
                        except:
                            pass
                
                elif platform == 'Lever':
                    if 'jobs.lever.co' in career_url:
                        company = career_url.split('jobs.lever.co/')[-1].split('/')[0]
                        api_url = f"https://api.lever.co/v0/postings/{company}?mode=json"
                
                elif platform == 'Ashby':
                    if 'jobs.ashbyhq.com' in career_url:
                        company = career_url.split('jobs.ashbyhq.com/')[-1].split('/')[0]
                        api_url = f"https://jobs.ashbyhq.com/{company}/jobs"
                
                if api_url:
                    print(f"📡 Found API URL: {api_url}")
                    return api_url, platform
                else:
                    print(f"⚠️  Platform detected but couldn't auto-extract API URL")
                    print(f"💡 Try manually looking at the page source for API calls")
                    return None, platform
        
        if not detected:
            print("\n❌ No known platform detected")
            print("\n💡 Manual detection steps:")
            print("1. Open the career page in Chrome")
            print("2. Press F12 to open DevTools")
            print("3. Go to Network tab")
            print("4. Filter by 'Fetch/XHR'")
            print("5. Refresh the page")
            print("6. Look for JSON responses with job data")
            print("7. Copy that URL and test it with this script")
        
        return None, None
        
    except Exception as e:
        print(f"❌ Error analyzing page: {e}")
        return None, None


def test_api_endpoint(api_url):
    """Test if an API endpoint works and show structure"""
    
    print(f"\n🧪 Testing API: {api_url}")
    print("=" * 70)
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        
        response = requests.get(api_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        # Try to find jobs array
        jobs_data = data
        jobs_path = None
        
        if isinstance(data, dict):
            if 'jobs' in data:
                jobs_data = data['jobs']
                jobs_path = 'jobs'
            elif 'data' in data:
                jobs_data = data['data']
                jobs_path = 'data'
            elif 'results' in data:
                jobs_data = data['results']
                jobs_path = 'results'
        
        print(f"\n✅ API is working!")
        print(f"📊 Response type: {type(data).__name__}")
        
        if jobs_path:
            print(f"📂 Jobs location: data['{jobs_path}']")
        
        if isinstance(jobs_data, list) and len(jobs_data) > 0:
            print(f"✅ Found {len(jobs_data)} jobs")
            
            # Analyze first job structure
            sample = jobs_data[0]
            print(f"\n📋 Sample job structure (first job):")
            print(json.dumps(sample, indent=2)[:800] + "...\n")
            
            # Suggest field mappings
            print("=" * 70)
            print("💡 SUGGESTED CONFIG FOR job_config.json:")
            print("=" * 70)
            
            config = {
                "name": "Company Name",
                "api_url": api_url,
            }
            
            # Find title field
            title_fields = [k for k in sample.keys() if 'title' in k.lower() or 'name' in k.lower()]
            if title_fields:
                config['api_title_field'] = title_fields[0]
            
            # Find department field
            dept_fields = [k for k in sample.keys() if 'department' in k.lower() or 'team' in k.lower()]
            if dept_fields:
                field = dept_fields[0]
                # Check if it's nested
                if isinstance(sample.get(field), dict):
                    config['api_department_field'] = f"{field}.name"
                elif isinstance(sample.get(field), list) and len(sample[field]) > 0:
                    config['api_department_field'] = f"{field}.0.name"
                else:
                    config['api_department_field'] = field
            
            # Find location field
            loc_fields = [k for k in sample.keys() if 'location' in k.lower()]
            if loc_fields:
                field = loc_fields[0]
                if isinstance(sample.get(field), dict):
                    config['api_location_field'] = f"{field}.name"
                else:
                    config['api_location_field'] = field
            
            # Find link field
            link_fields = [k for k in sample.keys() if 'url' in k.lower() or 'link' in k.lower()]
            if link_fields:
                config['api_link_field'] = link_fields[0]
            
            if jobs_path:
                config['api_jobs_path'] = jobs_path
            
            config['departments'] = ["Engineering", "Product", "Data"]
            config['locations'] = []
            
            print(json.dumps(config, indent=2))
            
            print("\n" + "=" * 70)
            print("📝 Copy the config above and add it to your job_config.json")
            print("=" * 70)
            
        else:
            print("\n⚠️  No jobs array found in response")
            if isinstance(data, dict):
                print(f"Available keys: {list(data.keys())}")
            print("\nFull response:")
            print(json.dumps(data, indent=2)[:1000] + "...")
        
        return True
        
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP Error {e.response.status_code}")
        print(f"Response: {e.response.text[:500]}")
        return False
    except json.JSONDecodeError:
        print(f"\n❌ Response is not valid JSON")
        print(f"Response preview: {response.text[:500]}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def main():
    """Main entry point"""
    
    print("\n" + "=" * 70)
    print("🔍 JOB BOARD API DETECTOR")
    print("=" * 70)
    
    if len(sys.argv) < 2:
        print("\n📖 Usage:")
        print("  python3 detect_api.py <URL>")
        print("\nExamples:")
        print("  python3 detect_api.py https://boards.greenhouse.io/stripe")
        print("  python3 detect_api.py https://jobs.lever.co/shopify")
        print("  python3 detect_api.py https://boards-api.greenhouse.io/v1/boards/stripe/jobs")
        print("\n💡 Tip: Use a company's career page URL to auto-detect the API")
        sys.exit(1)
    
    url = sys.argv[1]
    
    # Check if it's already an API URL
    if any(x in url.lower() for x in ['api', '.json', '/v0/', '/v1/']):
        print("🔗 Looks like an API URL, testing directly...\n")
        test_api_endpoint(url)
    else:
        print("🌐 Analyzing career page...\n")
        api_url, platform = find_api_endpoint(url)
        
        if api_url:
            print(f"\n✅ Success! Found {platform} API")
            test_api_endpoint(api_url)
        else:
            print("\n❌ Could not auto-detect API")
            if platform:
                print(f"\nDetected platform: {platform}")
                print("Try searching for their API documentation or use DevTools to find the endpoint")


if __name__ == "__main__":
    main()