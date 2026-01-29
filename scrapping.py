import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import hashlib


class JobMonitor:
    def __init__(self, config_file='job_config.json'):
        """Initialize the job monitor"""
        self.config = self.load_config(config_file)
        self.jobs_file = 'tracked_jobs.json'
        self.previous_jobs = self.load_previous_jobs()
    
    def load_config(self, config_file):
        """Load monitoring configuration"""
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
        return {"companies": []}
    
    def load_previous_jobs(self):
        """Load previously seen jobs"""
        if os.path.exists(self.jobs_file):
            with open(self.jobs_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_jobs(self):
        """Save current job state"""
        with open(self.jobs_file, 'w') as f:
            json.dump(self.previous_jobs, f, indent=2)
    
    def get_job_id(self, job):
        """Create unique ID for a job"""
        job_string = f"{job['company']}_{job['title']}_{job['department']}"
        return hashlib.md5(job_string.encode()).hexdigest()
    
    def get_nested_field(self, data, field_path):
        """Get nested field from dict (e.g., 'departments.0.name')"""
        if not field_path:
            return ''
        
        value = data
        for key in str(field_path).split('.'):
            if isinstance(value, dict):
                value = value.get(key, '')
            elif isinstance(value, list) and key.isdigit():
                idx = int(key)
                value = value[idx] if idx < len(value) else ''
            else:
                return ''
        
        return value
    
    def matches_filters(self, department, location, config):
        """Check if job matches department/location filters"""
        dept_filter = config.get('departments', [])
        loc_filter = config.get('locations', [])
        
        dept_match = not dept_filter or any(
            d.lower() in str(department).lower() for d in dept_filter
        )
        
        loc_match = not loc_filter or any(
            loc.lower() in str(location).lower() for loc in loc_filter
        )
        
        return dept_match and loc_match
    
    def fetch_jobs_from_api(self, company_config):
        """Fetch jobs from JSON API"""
        jobs = []
        
        try:
            print(f"\n📡 Fetching jobs from {company_config['name']} API...")
            print(f"🔗 URL: {company_config['api_url']}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
            }
            
            response = requests.get(company_config['api_url'], headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            # Navigate to jobs array
            jobs_data = data
            if isinstance(data, dict):
                if 'data' in data:
                    jobs_data = data['data']
                elif 'jobs' in data:
                    jobs_data = data['jobs']
                elif 'results' in data:
                    jobs_data = data['results']
            
            # Custom path if specified
            if 'api_jobs_path' in company_config:
                for key in company_config['api_jobs_path'].split('.'):
                    jobs_data = jobs_data[key]
            
            if not isinstance(jobs_data, list):
                print(f"⚠️ Expected list of jobs, got {type(jobs_data)}")
                return []
            
            print(f"✓ Found {len(jobs_data)} total jobs")
            
            # Extract jobs
            for job_data in jobs_data:
                try:
                    title = self.get_nested_field(job_data, company_config.get('api_title_field', 'title'))
                    department = self.get_nested_field(job_data, company_config.get('api_department_field', 'department'))
                    location = self.get_nested_field(job_data, company_config.get('api_location_field', 'location'))
                    link = self.get_nested_field(job_data, company_config.get('api_link_field', 'url'))
                    
                    # Make link absolute
                    if link and not link.startswith('http'):
                        base = company_config.get('base_url', company_config['api_url'].split('/api')[0])
                        link = base.rstrip('/') + '/' + link.lstrip('/')
                    
                    # Filter by department and location
                    if self.matches_filters(department, location, company_config):
                        jobs.append({
                            'company': company_config['name'],
                            'title': str(title),
                            'department': str(department),
                            'location': str(location),
                            'link': link,
                            'found_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                
                except Exception as e:
                    print(f"⚠️ Error parsing job: {e}")
                    continue
            
            print(f"✓ {len(jobs)} jobs match your filters")
            return jobs
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON response: {e}")
            return []
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return []
    
    def fetch_jobs_from_html(self, company_config):
        """Fetch jobs from HTML page"""
        jobs = []
        
        try:
            print(f"\n📡 Fetching jobs from {company_config['name']}...")
            print(f"🔗 URL: {company_config['url']}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(company_config['url'], headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all job listings
            job_elements = soup.select(company_config['job_selector'])
            print(f"✓ Found {len(job_elements)} total job listings")
            
            for job_elem in job_elements:
                try:
                    title_elem = job_elem.select_one(company_config['title_selector'])
                    dept_elem = job_elem.select_one(company_config['department_selector'])
                    link_elem = job_elem.select_one(company_config['link_selector'])
                    
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    department = dept_elem.get_text(strip=True) if dept_elem else "Unknown"
                    link = link_elem.get('href', '') if link_elem else ''
                    
                    # Make link absolute
                    if link and not link.startswith('http'):
                        base_url = '/'.join(company_config['url'].split('/')[:3])
                        link = base_url + link if link.startswith('/') else base_url + '/' + link
                    
                    # Filter
                    if self.matches_filters(department, '', company_config):
                        jobs.append({
                            'company': company_config['name'],
                            'title': title,
                            'department': department,
                            'location': '',
                            'link': link,
                            'found_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                
                except Exception as e:
                    continue
            
            print(f"✓ {len(jobs)} jobs match your filters")
            return jobs
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return []
    
    def fetch_jobs(self, company_config):
        """Route to appropriate fetch method"""
        if 'api_url' in company_config:
            return self.fetch_jobs_from_api(company_config)
        else:
            return self.fetch_jobs_from_html(company_config)
    
    def check_for_new_jobs(self):
        """Main monitoring loop"""
        print("=" * 70)
        print(f"🔍 JOB MONITOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        all_new_jobs = []
        
        for company in self.config['companies']:
            current_jobs = self.fetch_jobs(company)
            
            new_jobs = []
            for job in current_jobs:
                job_id = self.get_job_id(job)
                if job_id not in self.previous_jobs:
                    new_jobs.append(job)
                    self.previous_jobs[job_id] = job
            
            if new_jobs:
                print(f"\n🚨 {len(new_jobs)} NEW JOB(S) at {company['name']}!")
                print("-" * 70)
                for job in new_jobs:
                    print(f"\n  📋 {job['title']}")
                    print(f"  🏢 {job['department']}", end='')
                    if job.get('location'):
                        print(f" - {job['location']}", end='')
                    print()
                    if job.get('link'):
                        print(f"  🔗 {job['link']}")
                all_new_jobs.extend(new_jobs)
            else:
                print(f"✓ No new jobs at {company['name']}")
        
        self.save_jobs()
        
        print("\n" + "=" * 70)
        if all_new_jobs:
            print(f"🎯 TOTAL: {len(all_new_jobs)} new job(s)")
        else:
            print("✅ No new jobs found")
        print("=" * 70)
        
        return all_new_jobs


def main():
    monitor = JobMonitor()
    monitor.check_for_new_jobs()


if __name__ == "__main__":
    main()