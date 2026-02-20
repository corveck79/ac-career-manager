"""
AC Career Manager - First Run Setup Wizard
Auto-detects AC installation, scans cars, configures career
"""

import json
import os
from pathlib import Path
import re

class SetupWizard:
    """First-run setup wizard"""
    
    def __init__(self, config_path='config.json', career_path='career_data.json'):
        self.config_path = config_path
        self.career_path = career_path
        self.config = None
        self.ac_path = None
        
    def run(self):
        """Run complete setup wizard"""
        print("\n" + "="*60)
        print("  AC CAREER MANAGER - FIRST RUN SETUP")
        print("="*60 + "\n")
        
        # Check if config exists
        if self._config_exists():
            print("✓ Configuration already exists")
            return True
        
        # Step 1: Find AC
        print("\n[STEP 1] Locating Assetto Corsa...")
        self.ac_path = self._find_ac_installation()
        
        if not self.ac_path:
            print("✗ Could not find AC installation")
            return False
        
        print(f"✓ Found AC at: {self.ac_path}\n")
        
        # Step 2: Scan cars
        print("[STEP 2] Scanning installed cars...")
        available_cars = self._scan_available_cars()
        
        if not available_cars:
            print("✗ No cars found in AC installation")
            return False
        
        print(f"✓ Found {len(available_cars)} cars\n")
        
        # Step 3: Load base config
        print("[STEP 3] Loading configuration...")
        self.config = self._load_base_config()
        
        # Step 4: Configure teams with available cars
        print("[STEP 4] Configuring teams with available cars...")
        self._configure_teams_with_cars(available_cars)
        
        # Step 5: Save config
        print("[STEP 5] Saving configuration...")
        self._save_config()
        
        print("\n" + "="*60)
        print("✓ SETUP COMPLETE!")
        print("="*60)
        print(f"\nConfiguration saved to: {self.config_path}")
        print(f"AC Installation: {self.ac_path}")
        print(f"Available cars: {len(available_cars)}")
        print("\nYou're ready to start your career!")
        print("Launch the app and click 'New Career' to begin.\n")
        
        return True
    
    def _config_exists(self):
        """Check if config already exists"""
        if not os.path.exists(self.config_path):
            return False
        
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                # Check if it has AC path set
                return 'paths' in config and 'ac_install' in config['paths']
        except:
            return False
    
    def _find_ac_installation(self):
        """Auto-detect AC installation"""
        common_paths = [
            "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Assetto Corsa",
            "C:\\Program Files\\Steam\\steamapps\\common\\Assetto Corsa",
            "D:\\Steam\\steamapps\\common\\Assetto Corsa",
            "E:\\Games\\Assetto Corsa",
        ]
        
        # Check common paths
        for path in common_paths:
            if os.path.exists(path):
                if os.path.exists(os.path.join(path, 'AssettoCorsa.exe')):
                    return path
        
        # Ask user
        print("\nCould not auto-detect AC installation.")
        print("Please enter your AC installation path:")
        print("(e.g., C:\\Program Files (x86)\\Steam\\steamapps\\common\\Assetto Corsa)\n")
        
        while True:
            user_path = input("AC Installation Path: ").strip().strip('"')
            
            if os.path.exists(user_path):
                if os.path.exists(os.path.join(user_path, 'AssettoCorsa.exe')):
                    return user_path
            
            print("✗ Invalid path. Please try again.")
        
        return None
    
    def _scan_available_cars(self):
        """Scan AC directory for available cars"""
        cars_dir = os.path.join(self.ac_path, 'content', 'cars')
        available_cars = {}
        
        if not os.path.exists(cars_dir):
            print(f"Warning: Cars directory not found at {cars_dir}")
            return available_cars
        
        # Get list of car folders
        try:
            for car_folder in os.listdir(cars_dir):
                car_path = os.path.join(cars_dir, car_folder)
                if os.path.isdir(car_path):
                    available_cars[car_folder] = {
                        'folder': car_folder,
                        'available': True
                    }
        except Exception as e:
            print(f"Warning: Error scanning cars: {e}")
        
        return available_cars
    
    def _load_base_config(self):
        """Load base configuration template"""
        # Read the default config.json as template
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except:
            # If it doesn't exist, create minimal config
            return {
                "app": {"name": "AC Career Manager", "version": "1.0.0"},
                "paths": {"ac_install": self.ac_path},
                "difficulty": {
                    "base_ai_level": 85,
                    "ai_variance": 1.5,
                    "tier_multipliers": {"mx5_cup": -4, "gt4": -2, "gt3": 0, "wec": 1.5}
                },
                "seasons": {"races_per_tier": 10},
                "tiers": {}
            }
    
    def _configure_teams_with_cars(self, available_cars):
        """Configure teams based on available cars"""
        
        # Map AC car folders to tier assignments
        car_mapping = {
            # MX5
            'ks_mazda_mx5_cup': 'mx5_cup',
            'ks_mazda_miata': 'mx5_cup',
            
            # GT4
            'ks_porsche_cayman_gt4_clubsport': 'gt4',
            'ks_porsche_cayman_gt4_std': 'gt4',
            'lotus_2_eleven_gt4': 'gt4',
            'ks_bmw_m4_gt4': 'gt4',
            'ks_aston_martin_v8_vantage_gt3': 'gt4',
            'ks_mercedes_amg_gt4': 'gt4',
            
            # GT3
            'ks_ferrari_488_gt3': 'gt3',
            'ks_porsche_911_gt3_2015': 'gt3',
            'ks_porsche_911_gt3_rs_weissach_package': 'gt3',
            'ks_aston_martin_v12_vantage_gt3': 'gt3',
            'ks_lamborghini_huracan_gt3': 'gt3',
            'ks_bmw_m4_gt3': 'gt3',
            'ks_mclaren_650s_gt3': 'gt3',
            'ks_mercedes_amg_gt3': 'gt3',
            'ks_nissan_gtr_nismo_gt3': 'gt3',
            'ks_bentley_continental_gt3': 'gt3',
            'ks_mclaren_mp412c_gt3': 'gt3',
            'ks_lamborghini_gallardo_gt3': 'gt3',
            'ks_bmw_z4_gt3': 'gt3',
            'ks_mercedes_sls_gt3': 'gt3',
        }
        
        # Group available cars by tier
        cars_by_tier = {
            'mx5_cup': [],
            'gt4': [],
            'gt3': [],
            'wec': []
        }
        
        print("\nScanning car assignments:")
        for car_id, car_info in available_cars.items():
            if car_id in car_mapping:
                tier = car_mapping[car_id]
                cars_by_tier[tier].append(car_id)
                print(f"  ✓ {car_id} → {tier}")
        
        # Update config with available cars
        print("\nConfiguring teams...")
        for tier_key, tier_cars in cars_by_tier.items():
            if tier_key not in self.config['tiers']:
                self.config['tiers'][tier_key] = self._get_tier_template(tier_key)
            
            # Only include teams that have available cars
            teams = []
            team_names = [
                "Mazda Academy", "Apex Racing", "Speed Demons", "Track Masters",
                "Racing Academy", "Performance Driving", "Midnight Racers", "Circuit Specialists",
                "Road Warriors", "Elite Motorsports", "Thunder Racing", "Victory Lane",
                "Turbo Charge", "Precision Drivers",
                "Ferrari AF Corse", "Porsche Weissach", "BMW M Motorsport", "Mercedes AMG",
                "Aston Martin Racing", "Lotus Hethel", "Lamborghini Squad", "Team Italia",
                "Porsche Customer", "Racing Legends", "Alpine Competition", "Circuit Kings",
                "Turbocharged", "Speed Factory", "Velocity Racing", "Apex Precision",
                "Ferrari Rosso Corsa", "Porsche Factory", "McLaren GT", "Aston Martin Factory",
                "Ferrari Rosso Corsa", "Porsche GT", "BMW Motorsport", "Lamborghini Squadra",
                "Mercedes AMG Racing", "Nissan Nismo", "Bentley Racing", "McLaren Racing",
                "Rising Stars", "Underdog Racing",
                "Ferrari Endurance", "Porsche Endurance", "McLaren LMP", "Aston Martin WEC",
                "AF Corse Elite", "Porsche GT Elite", "BMW Endurance", "Lamborghini Elite",
                "Rising Champions", "Victory Motors"
            ]
            
            # Create teams with available cars
            for i, car_id in enumerate(tier_cars):
                if i < len(team_names):
                    team = {
                        "name": team_names[i],
                        "car": car_id,
                        "tier": "factory" if i == 0 else ("semi" if i < 4 else "customer"),
                        "performance": -i * 0.1
                    }
                    teams.append(team)
            
            # If no cars available for this tier, use defaults from config
            if not teams and tier_key in self.config['tiers'] and 'teams' in self.config['tiers'][tier_key]:
                teams = self.config['tiers'][tier_key]['teams']
            
            self.config['tiers'][tier_key]['teams'] = teams
            print(f"  ✓ {tier_key}: {len(teams)} teams configured")
    
    def _get_tier_template(self, tier_key):
        """Get tier template from config"""
        templates = {
            'mx5_cup': {
                'name': 'MX5 Cup',
                'description': 'Junior One-Make Championship',
                'order': 0,
                'ai_difficulty': -4,
                'tracks': ['silverstone', 'donington', 'brands_hatch', 'snetterton', 'oulton_park'],
                'race_format': {'laps': 20, 'time_limit_minutes': 45, 'weather': 'clear'},
                'teams': []
            },
            'gt4': {
                'name': 'GT4 SuperCup',
                'description': 'International GT4 Championship',
                'order': 1,
                'ai_difficulty': -2,
                'tracks': ['silverstone', 'donington', 'spa', 'brands_hatch', 'snetterton'],
                'race_format': {'laps': 18, 'time_limit_minutes': 60, 'weather': 'variable'},
                'teams': []
            },
            'gt3': {
                'name': 'British GT GT3',
                'description': 'Elite GT3 Championship',
                'order': 2,
                'ai_difficulty': 0,
                'tracks': ['silverstone', 'donington', 'spa', 'monza', 'paul_ricard', 'laguna_seca'],
                'race_format': {'laps': 20, 'time_limit_minutes': 90, 'weather': 'variable'},
                'teams': []
            },
            'wec': {
                'name': 'WEC / Elite Endurance',
                'description': 'World Endurance Championship Elite',
                'order': 3,
                'ai_difficulty': 1.5,
                'tracks': ['silverstone', 'spa', 'monza', 'paul_ricard'],
                'race_format': {'laps': 40, 'time_limit_minutes': 180, 'weather': 'variable'},
                'teams': []
            }
        }
        return templates.get(tier_key, {})
    
    def _save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"✗ Error saving config: {e}")
            return False


def check_and_run_setup(config_path='config.json'):
    """Check if setup is needed and run wizard"""
    wizard = SetupWizard(config_path)
    
    if not wizard._config_exists():
        return wizard.run()
    
    return True


if __name__ == '__main__':
    wizard = SetupWizard()
    wizard.run()
