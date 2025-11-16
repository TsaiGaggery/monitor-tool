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
            output_dir: Base directory to save exported files. Defaults to ./reports/
        """
        if output_dir is None:
            # Use reports directory in project root
            output_dir = 'reports'
        
        self.base_output_dir = Path(output_dir)
        self.session_data = []
        self.start_time = datetime.now()
        
        # Create date-based subdirectory (YYYY-MM-DD format)
        date_str = self.start_time.strftime('%Y-%m-%d')
        self.output_dir = self.base_output_dir / date_str
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
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
        """Generate interactive HTML report with charts.
        
        Args:
            stats: Statistics dictionary
            
        Returns:
            HTML string with interactive charts
        """
        # Calculate duration from actual data timestamps
        if self.session_data and len(self.session_data) >= 2:
            try:
                # Parse first and last timestamps
                first_ts = self.session_data[0].get('timestamp', '')
                last_ts = self.session_data[-1].get('timestamp', '')
                
                if first_ts and last_ts:
                    # Try to parse timestamps
                    first_time = datetime.strptime(first_ts, '%Y-%m-%d %H:%M:%S')
                    last_time = datetime.strptime(last_ts, '%Y-%m-%d %H:%M:%S')
                    duration = last_time - first_time
                else:
                    duration = datetime.now() - self.start_time
            except:
                duration = datetime.now() - self.start_time
        else:
            duration = datetime.now() - self.start_time
        
        # Prepare chart data - extract ALL available data
        timestamps = []
        
        # CPU data arrays
        cpu_usage_total = []
        cpu_usage_per_core = []  # List of lists for each core
        cpu_freq_avg = []
        cpu_freq_per_core = []  # List of lists for each core
        cpu_temps = []  # List of lists for each temp sensor
        
        # GPU data arrays
        gpu_usage = []
        gpu_memory_used = []
        gpu_memory_util = []
        gpu_freq = []
        gpu_temp = []
        gpu_power = []
        
        # Memory data arrays
        memory_percent = []
        memory_used = []
        memory_available = []
        swap_percent = []
        
        # NPU data arrays
        npu_usage = []
        
        # Track max cores/temps for consistent array sizes
        max_cpu_cores = 0
        max_temp_sensors = 0
        
        for sample in self.session_data:
            # Extract timestamp
            if 'timestamp' in sample:
                timestamps.append(sample['timestamp'])
            else:
                timestamps.append(len(timestamps))
            
            # CPU data extraction
            if 'cpu' in sample:
                cpu_data = sample['cpu']
                if isinstance(cpu_data, dict):
                    # Total CPU usage
                    usage = cpu_data.get('usage', {})
                    if isinstance(usage, dict):
                        cpu_usage_total.append(usage.get('total', 0))
                        # Per-core usage
                        per_core = usage.get('per_core', [])
                        if per_core:
                            max_cpu_cores = max(max_cpu_cores, len(per_core))
                            cpu_usage_per_core.append(per_core)
                    else:
                        cpu_usage_total.append(usage if usage else 0)
                        cpu_usage_per_core.append([])
                    
                    # CPU frequency
                    freq = cpu_data.get('frequency', {})
                    if isinstance(freq, dict):
                        cpu_freq_avg.append(freq.get('average', 0))
                        # Per-core frequency - keep full objects
                        per_core_freq = freq.get('per_core', [])
                        if per_core_freq:
                            cpu_freq_per_core.append(per_core_freq)
                        else:
                            cpu_freq_per_core.append([])
                    else:
                        cpu_freq_avg.append(freq if freq else 0)
                        cpu_freq_per_core.append([])
                    
                    # CPU temperature
                    temp = cpu_data.get('temperature', {})
                    if isinstance(temp, dict):
                        coretemp = temp.get('coretemp', [])
                        if coretemp:
                            max_temp_sensors = max(max_temp_sensors, len(coretemp))
                            # Keep full sensor info (label + current)
                            cpu_temps.append(coretemp)
                        else:
                            cpu_temps.append([])
                    else:
                        cpu_temps.append([])
            
            # GPU data extraction
            if 'gpu' in sample:
                gpu_data = sample['gpu']
                if isinstance(gpu_data, dict):
                    if 'gpus' in gpu_data and isinstance(gpu_data['gpus'], list) and len(gpu_data['gpus']) > 0:
                        first_gpu = gpu_data['gpus'][0]
                        gpu_usage.append(first_gpu.get('gpu_util', 0))
                        gpu_memory_used.append(first_gpu.get('memory_used', 0))
                        gpu_memory_util.append(first_gpu.get('memory_util', 0))
                        gpu_freq.append(first_gpu.get('gpu_clock', 0))
                        gpu_temp.append(first_gpu.get('temperature', 0))
                        gpu_power.append(first_gpu.get('power', 0))
                    else:
                        gpu_usage.append(gpu_data.get('gpu_util', 0))
                        gpu_memory_used.append(gpu_data.get('memory_used', 0))
                        gpu_memory_util.append(gpu_data.get('memory_util', 0))
                        gpu_freq.append(gpu_data.get('gpu_clock', 0))
                        gpu_temp.append(gpu_data.get('temperature', 0))
                        gpu_power.append(gpu_data.get('power', 0))
            else:
                gpu_usage.append(0)
                gpu_memory_used.append(0)
                gpu_memory_util.append(0)
                gpu_freq.append(0)
                gpu_temp.append(0)
                gpu_power.append(0)
            
            # Memory data extraction
            if 'memory' in sample:
                mem_data = sample['memory']
                if isinstance(mem_data, dict):
                    if 'memory' in mem_data and isinstance(mem_data['memory'], dict):
                        mem_info = mem_data['memory']
                        memory_percent.append(mem_info.get('percent', 0))
                        memory_used.append(mem_info.get('used', 0))
                        memory_available.append(mem_info.get('available', 0))
                    else:
                        memory_percent.append(mem_data.get('percent', 0))
                        memory_used.append(mem_data.get('used', 0))
                        memory_available.append(mem_data.get('available', 0))
                    
                    # Swap data
                    if 'swap' in mem_data and isinstance(mem_data['swap'], dict):
                        swap_percent.append(mem_data['swap'].get('percent', 0))
                    else:
                        swap_percent.append(0)
            
            # NPU data extraction
            if 'npu' in sample:
                npu_data = sample['npu']
                if isinstance(npu_data, dict):
                    npu_usage.append(npu_data.get('utilization', 0))
        
        # Convert to JSON for JavaScript
        import json
        chart_data = {
            'timestamps': timestamps,
            'cpu': {
                'usage_total': cpu_usage_total,
                'usage_per_core': cpu_usage_per_core,
                'freq_avg': cpu_freq_avg,
                'freq_per_core': cpu_freq_per_core,
                'temps': cpu_temps,
                'max_cores': max_cpu_cores,
                'max_temp_sensors': max_temp_sensors
            },
            'gpu': {
                'usage': gpu_usage,
                'memory_used': gpu_memory_used,
                'memory_util': gpu_memory_util,
                'freq': gpu_freq,
                'temp': gpu_temp,
                'power': gpu_power
            },
            'memory': {
                'percent': memory_percent,
                'used': memory_used,
                'available': memory_available,
                'swap_percent': swap_percent
            },
            'npu': {
                'usage': npu_usage
            }
        }
        
        # Calculate statistics
        stats = self._calculate_statistics()
        
        # Generate NPU section if data exists
        npu_section = ''
        if npu_usage and any(npu_usage):
            npu_section = '<h3 style="color: #14ffec; margin-top: 30px;">🤖 NPU Metrics</h3><div class="chart-container"><div class="chart-title">NPU Usage (%)</div><canvas id="npuUsageChart"></canvas></div>'
        
        # Generate statistics table rows
        stats_rows = ''
        sorted_metrics = sorted(stats.items())
        for metric, values in sorted_metrics:
            stats_rows += f'''                <tr>
                    <td class="metric-name">{metric}</td>
                    <td class="value-min">{values['min']:.2f}</td>
                    <td class="value-max">{values['max']:.2f}</td>
                    <td class="value-avg">{values['avg']:.2f}</td>
                    <td>{values['samples']}</td>
                </tr>
'''
        
        # Load HTML template
        template_path = Path(__file__).parent.parent.parent / 'templates' / 'report.html'
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Template not found at {template_path}")
        
        # Replace template variables
        html = template.replace('{{ start_time }}', self.start_time.strftime('%Y-%m-%d %H:%M:%S'))
        html = html.replace('{{ duration }}', str(duration))
        html = html.replace('{{ data_points }}', str(len(self.session_data)))
        html = html.replace('{{ chart_data_json }}', json.dumps(chart_data).replace("'", "\\'"))
        html = html.replace('{{ npu_section }}', npu_section)
        html = html.replace('{{ stats_rows }}', stats_rows)
        html = html.replace('{{ report_time }}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        return html
    
    def clear_session(self):
        """Clear current session data and start a new session."""
        self.session_data = []
        self.start_time = datetime.now()
        
        # Update output directory to new date
        date_str = self.start_time.strftime('%Y-%m-%d')
        self.output_dir = self.base_output_dir / date_str
        self.output_dir.mkdir(parents=True, exist_ok=True)


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
