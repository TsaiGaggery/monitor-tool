#!/usr/bin/env python3
"""Data export module for saving monitoring data to various formats."""

import json
import csv
import os
from datetime import datetime
from typing import Dict, List
from pathlib import Path


class DataExporter:
    """Export monitoring data to CSV, JSON, or HTML formats."""
    
    def __init__(self, output_dir: str = None):
        """Initialize data exporter.
        
        Args:
            output_dir: Directory to save exported files. Defaults to ~/monitor-tool-exports/
        """
        if output_dir is None:
            output_dir = os.path.expanduser('~/monitor-tool-exports')
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.session_data = []
        self.start_time = datetime.now()
    
    def add_sample(self, data: Dict):
        """Add a monitoring sample to the session.
        
        Args:
            data: Dictionary containing monitoring data with timestamp
        """
        self.session_data.append(data.copy())
    
    def export_csv(self, filename: str = None) -> str:
        """Export session data to CSV format.
        
        Args:
            filename: Output filename. Auto-generated if None.
            
        Returns:
            Path to the exported file
        """
        if filename is None:
            timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
            filename = f'monitoring_data_{timestamp}.csv'
        
        filepath = self.output_dir / filename
        
        if not self.session_data:
            raise ValueError("No data to export")
        
        # Extract all unique keys from all samples
        all_keys = set()
        for sample in self.session_data:
            all_keys.update(self._flatten_dict(sample).keys())
        
        all_keys = sorted(all_keys)
        
        with open(filepath, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=all_keys)
            writer.writeheader()
            
            for sample in self.session_data:
                flat_data = self._flatten_dict(sample)
                writer.writerow(flat_data)
        
        return str(filepath)
    
    def export_json(self, filename: str = None) -> str:
        """Export session data to JSON format.
        
        Args:
            filename: Output filename. Auto-generated if None.
            
        Returns:
            Path to the exported file
        """
        if filename is None:
            timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
            filename = f'monitoring_data_{timestamp}.json'
        
        filepath = self.output_dir / filename
        
        if not self.session_data:
            raise ValueError("No data to export")
        
        export_data = {
            'session_info': {
                'start_time': self.start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'sample_count': len(self.session_data)
            },
            'data': self.session_data
        }
        
        with open(filepath, 'w') as jsonfile:
            json.dump(export_data, jsonfile, indent=2)
        
        return str(filepath)
    
    def export_html(self, filename: str = None) -> str:
        """Export session data to HTML report format.
        
        Args:
            filename: Output filename. Auto-generated if None.
            
        Returns:
            Path to the exported file
        """
        if filename is None:
            timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
            filename = f'monitoring_report_{timestamp}.html'
        
        filepath = self.output_dir / filename
        
        if not self.session_data:
            raise ValueError("No data to export")
        
        # Calculate statistics
        stats = self._calculate_statistics()
        
        html_content = self._generate_html_report(stats)
        
        with open(filepath, 'w') as htmlfile:
            htmlfile.write(html_content)
        
        return str(filepath)
    
    def _flatten_dict(self, d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
        """Flatten nested dictionary.
        
        Args:
            d: Dictionary to flatten
            parent_key: Parent key for nested items
            sep: Separator between parent and child keys
            
        Returns:
            Flattened dictionary
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # Convert list to string representation
                items.append((new_key, str(v)))
            else:
                items.append((new_key, v))
        return dict(items)
    
    def _calculate_statistics(self) -> Dict:
        """Calculate statistics from session data.
        
        Returns:
            Dictionary containing min, max, avg for various metrics
        """
        stats = {}
        
        if not self.session_data:
            return stats
        
        # Extract numeric values for each key
        numeric_data = {}
        for sample in self.session_data:
            flat_sample = self._flatten_dict(sample)
            for key, value in flat_sample.items():
                if isinstance(value, (int, float)):
                    if key not in numeric_data:
                        numeric_data[key] = []
                    numeric_data[key].append(value)
        
        # Calculate min, max, avg
        for key, values in numeric_data.items():
            if values:
                stats[key] = {
                    'min': min(values),
                    'max': max(values),
                    'avg': sum(values) / len(values),
                    'samples': len(values)
                }
        
        return stats
    
    def _generate_html_report(self, stats: Dict) -> str:
        """Generate HTML report content.
        
        Args:
            stats: Statistics dictionary
            
        Returns:
            HTML string
        """
        duration = datetime.now() - self.start_time
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>System Monitoring Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #1e1e1e;
            color: #e0e0e0;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            color: #14ffec;
            border-bottom: 2px solid #0d7377;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #0d7377;
            margin-top: 30px;
        }}
        .summary {{
            background-color: #2a2a2a;
            border-left: 4px solid #0d7377;
            padding: 15px;
            margin: 20px 0;
        }}
        .summary-item {{
            display: inline-block;
            margin-right: 30px;
        }}
        .summary-label {{
            color: #888;
            font-size: 0.9em;
        }}
        .summary-value {{
            color: #14ffec;
            font-size: 1.2em;
            font-weight: bold;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background-color: #2a2a2a;
        }}
        th {{
            background-color: #0d7377;
            color: #e0e0e0;
            padding: 12px;
            text-align: left;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #3a3a3a;
        }}
        tr:hover {{
            background-color: #333;
        }}
        .metric-name {{
            color: #14ffec;
            font-weight: bold;
        }}
        .value-min {{
            color: #4ecdc4;
        }}
        .value-max {{
            color: #ff6b6b;
        }}
        .value-avg {{
            color: #ffd93d;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #3a3a3a;
            text-align: center;
            color: #888;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>System Monitoring Report</h1>
        
        <div class="summary">
            <div class="summary-item">
                <div class="summary-label">Start Time</div>
                <div class="summary-value">{self.start_time.strftime('%Y-%m-%d %H:%M:%S')}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Duration</div>
                <div class="summary-value">{duration}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Samples</div>
                <div class="summary-value">{len(self.session_data)}</div>
            </div>
        </div>
        
        <h2>Performance Statistics</h2>
        <table>
            <thead>
                <tr>
                    <th>Metric</th>
                    <th>Minimum</th>
                    <th>Maximum</th>
                    <th>Average</th>
                    <th>Samples</th>
                </tr>
            </thead>
            <tbody>
"""
        
        # Sort metrics for better readability
        sorted_metrics = sorted(stats.items())
        
        for metric, values in sorted_metrics:
            html += f"""                <tr>
                    <td class="metric-name">{metric}</td>
                    <td class="value-min">{values['min']:.2f}</td>
                    <td class="value-max">{values['max']:.2f}</td>
                    <td class="value-avg">{values['avg']:.2f}</td>
                    <td>{values['samples']}</td>
                </tr>
"""
        
        html += """            </tbody>
        </table>
        
        <div class="footer">
            Generated by Monitor Tool - Pro Edition
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def clear_session(self):
        """Clear current session data and start a new session."""
        self.session_data = []
        self.start_time = datetime.now()


if __name__ == '__main__':
    # Test the exporter
    exporter = DataExporter()
    
    # Add some test samples
    for i in range(10):
        exporter.add_sample({
            'timestamp': datetime.now().isoformat(),
            'cpu': {
                'usage': 50 + i,
                'temp': 60 + i * 0.5
            },
            'gpu': {
                'usage': 30 + i * 2,
                'memory': 2000 + i * 100
            }
        })
    
    # Export to all formats
    print("CSV:", exporter.export_csv())
    print("JSON:", exporter.export_json())
    print("HTML:", exporter.export_html())
