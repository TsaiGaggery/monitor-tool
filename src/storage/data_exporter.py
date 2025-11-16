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
                    from datetime import datetime
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
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>System Monitoring Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #1e1e1e;
            color: #e0e0e0;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
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
            display: flex;
            gap: 40px;
        }}
        .summary-item {{
            flex: 1;
        }}
        .summary-label {{
            color: #888;
            font-size: 0.9em;
            margin-bottom: 5px;
        }}
        .summary-value {{
            color: #14ffec;
            font-size: 1.3em;
            font-weight: bold;
        }}
        .chart-container {{
            background-color: #2a2a2a;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            position: relative;
            height: 350px;
        }}
        .chart-title {{
            color: #14ffec;
            font-size: 1.1em;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .chart-hint {{
            color: #888;
            font-size: 0.85em;
            margin-bottom: 10px;
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
            position: sticky;
            top: 0;
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
        .value-min {{ color: #4ecdc4; }}
        .value-max {{ color: #ff6b6b; }}
        .value-avg {{ color: #ffd93d; }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #3a3a3a;
            text-align: center;
            color: #888;
            font-size: 0.9em;
        }}
        .grid-2col {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        h3 {{
            color: #4ecdc4;
            margin-bottom: 15px;
            font-size: 1.2em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 System Monitoring Report</h1>
        
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
                <div class="summary-label">Data Points</div>
                <div class="summary-value">{len(self.session_data)}</div>
            </div>
        </div>
        
        <script>
            // Hide GPU temp/power containers if no data
            window.addEventListener('DOMContentLoaded', () => {{
                const chartData = JSON.parse('{json.dumps(chart_data).replace("'", "\\'")}');
                
                // Hide GPU temperature chart if all zeros
                if (!chartData.gpu.temp || chartData.gpu.temp.every(t => t === 0)) {{
                    const tempContainer = document.getElementById('gpuTempContainer');
                    if (tempContainer) tempContainer.style.display = 'none';
                }}
                
                // Hide GPU power chart if all zeros
                if (!chartData.gpu.power || chartData.gpu.power.every(p => p === 0)) {{
                    const powerContainer = document.getElementById('gpuPowerContainer');
                    if (powerContainer) powerContainer.style.display = 'none';
                }}
                
                // Hide swap chart if all zeros
                if (!chartData.memory.swap_percent || chartData.memory.swap_percent.every(s => s === 0)) {{
                    const swapContainer = document.getElementById('swapContainer');
                    if (swapContainer) swapContainer.style.display = 'none';
                }}
            }});
        </script>
        
        <h2>📈 Interactive Time Series Charts</h2>
        <p class="chart-hint" style="color: #888; margin-bottom: 20px;">
            💡 <strong>Tip:</strong> Use mouse wheel to zoom, drag to pan, double-click to reset
        </p>
        
        <!-- CPU Charts Section -->
        <h3 style="color: #14ffec; margin-top: 30px;">🖥️ CPU Metrics</h3>
        
        <div class="grid-2col">
            <div class="chart-container">
                <div class="chart-title">CPU Usage - Total (%)</div>
                <canvas id="cpuUsageChart"></canvas>
            </div>
            <div class="chart-container">
                <div class="chart-title">CPU Usage - Per Core (%)</div>
                <canvas id="cpuPerCoreChart"></canvas>
            </div>
        </div>
        
        <div class="grid-2col">
            <div class="chart-container">
                <div class="chart-title">CPU Frequency - Average (MHz)</div>
                <canvas id="cpuFreqChart"></canvas>
            </div>
            <div class="chart-container">
                <div class="chart-title">CPU Frequency - Per Core (MHz)</div>
                <canvas id="cpuPerCoreFreqChart"></canvas>
            </div>
        </div>
        
        <div class="chart-container">
            <div class="chart-title">🌡️ CPU Temperature (°C)</div>
            <canvas id="cpuTempChart"></canvas>
        </div>
        
        <!-- GPU Charts Section -->
        <h3 style="color: #14ffec; margin-top: 30px;">🎮 GPU Metrics</h3>
        
        <div class="grid-2col">
            <div class="chart-container">
                <div class="chart-title">GPU Usage (%) & Frequency (MHz)</div>
                <canvas id="gpuUsageChart"></canvas>
            </div>
            <div class="chart-container">
                <div class="chart-title">GPU Memory (MB) & Utilization (%)</div>
                <canvas id="gpuMemoryChart"></canvas>
            </div>
        </div>
        
        <div class="grid-2col">
            <div class="chart-container" id="gpuTempContainer">
                <div class="chart-title">🌡️ GPU Temperature (°C)</div>
                <canvas id="gpuTempChart"></canvas>
            </div>
            <div class="chart-container" id="gpuPowerContainer">
                <div class="chart-title">⚡ GPU Power Consumption (W)</div>
                <canvas id="gpuPowerChart"></canvas>
            </div>
        </div>
        
        <!-- Memory Charts Section -->
        <h3 style="color: #14ffec; margin-top: 30px;">🧠 Memory Metrics</h3>
        
        <div class="grid-2col">
            <div class="chart-container">
                <div class="chart-title">Memory Usage (%)</div>
                <canvas id="memoryChart"></canvas>
            </div>
            <div class="chart-container">
                <div class="chart-title">Memory Details (GB)</div>
                <canvas id="memoryDetailsChart"></canvas>
            </div>
        </div>
        
        <div class="chart-container" id="swapContainer">
            <div class="chart-title">💿 Swap Usage (%)</div>
            <canvas id="swapChart"></canvas>
        </div>
        
        <!-- NPU Chart if available -->
        {'<h3 style="color: #14ffec; margin-top: 30px;">🤖 NPU Metrics</h3><div class="chart-container"><div class="chart-title">NPU Usage (%)</div><canvas id="npuUsageChart"></canvas></div>' if npu_usage and any(npu_usage) else ''}
        
        <h2>📊 Statistics Summary</h2>
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
        
        html += f"""            </tbody>
        </table>
        
        <div class="footer">
            Generated by Monitor Tool - Pro Edition<br>
            Report created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
    
    <script>
        const chartData = {json.dumps(chart_data)};
        
        // Common chart configuration
        const commonOptions = {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                legend: {{
                    display: true,
                    labels: {{ color: '#e0e0e0' }}
                }},
                zoom: {{
                    pan: {{
                        enabled: true,
                        mode: 'x',
                    }},
                    zoom: {{
                        wheel: {{
                            enabled: true,
                        }},
                        pinch: {{
                            enabled: true
                        }},
                        mode: 'x',
                    }}
                }}
            }},
            scales: {{
                x: {{
                    title: {{
                        display: true,
                        text: 'Time',
                        color: '#e0e0e0'
                    }},
                    ticks: {{ 
                        color: '#888',
                        maxRotation: 45,
                        minRotation: 45
                    }},
                    grid: {{ color: '#3a3a3a' }}
                }},
                y: {{
                    ticks: {{ color: '#888' }},
                    grid: {{ color: '#3a3a3a' }}
                }}
            }}
        }};
        
        // CPU Usage (Total) Chart
        new Chart(document.getElementById('cpuUsageChart'), {{
            type: 'line',
            data: {{
                labels: chartData.timestamps,
                datasets: [{{
                    label: 'CPU Usage (Total)',
                    data: chartData.cpu.usage_total,
                    borderColor: '#ff6b6b',
                    backgroundColor: 'rgba(255, 107, 107, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true
                }}]
            }},
            options: {{
                ...commonOptions,
                scales: {{
                    ...commonOptions.scales,
                    y: {{
                        ...commonOptions.scales.y,
                        title: {{ display: true, text: 'Usage (%)', color: '#e0e0e0' }},
                        min: 0,
                        max: 100
                    }}
                }}
            }}
        }});
        
        // CPU Usage Per-Core Chart
        const cpuCoreColors = ['#ff6b6b', '#ffd93d', '#4ecdc4', '#95e1d3', '#c589e8', '#ff9ff3', 
                               '#feca57', '#48dbfb', '#ff6348', '#1dd1a1', '#10ac84', '#ee5a6f'];
        const coreDatasets = [];
        for (let i = 0; i < chartData.cpu.max_cores; i++) {{
            coreDatasets.push({{
                label: `Core ${{i}}`,
                data: chartData.cpu.usage_per_core.map(cores => cores[i] || 0),
                borderColor: cpuCoreColors[i % cpuCoreColors.length],
                backgroundColor: 'transparent',
                borderWidth: 1.5,
                tension: 0.3,
                fill: false,
                hidden: i >= 4  // Hide cores 4+ by default, click legend to show
            }});
        }}
        new Chart(document.getElementById('cpuPerCoreChart'), {{
            type: 'line',
            data: {{
                labels: chartData.timestamps,
                datasets: coreDatasets
            }},
            options: {{
                ...commonOptions,
                plugins: {{
                    ...commonOptions.plugins,
                    legend: {{
                        ...commonOptions.plugins.legend,
                        onClick: function(e, legendItem, legend) {{
                            // Default Chart.js legend click behavior
                            const index = legendItem.datasetIndex;
                            const ci = legend.chart;
                            const meta = ci.getDatasetMeta(index);
                            meta.hidden = meta.hidden === null ? !ci.data.datasets[index].hidden : null;
                            ci.update();
                        }}
                    }}
                }},
                scales: {{
                    ...commonOptions.scales,
                    y: {{
                        ...commonOptions.scales.y,
                        title: {{ display: true, text: 'Usage (%)', color: '#e0e0e0' }},
                        min: 0,
                        max: 100
                    }}
                }}
            }}
        }});
        
        // CPU Average Frequency Chart
        new Chart(document.getElementById('cpuFreqChart'), {{
            type: 'line',
            data: {{
                labels: chartData.timestamps,
                datasets: [{{
                    label: 'CPU Frequency (Avg)',
                    data: chartData.cpu.freq_avg,
                    borderColor: '#ffd93d',
                    backgroundColor: 'rgba(255, 217, 61, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true
                }}]
            }},
            options: {{
                ...commonOptions,
                scales: {{
                    ...commonOptions.scales,
                    y: {{
                        ...commonOptions.scales.y,
                        title: {{ display: true, text: 'Frequency (MHz)', color: '#e0e0e0' }}
                    }}
                }}
            }}
        }});
        
        // CPU Per-Core Frequency Chart
        const freqDatasets = [];
        for (let i = 0; i < chartData.cpu.max_cores; i++) {{
            freqDatasets.push({{
                label: `Core ${{i}} (Current)`,
                data: chartData.cpu.freq_per_core.map(cores => cores[i] ? cores[i].current : 0),
                borderColor: cpuCoreColors[i % cpuCoreColors.length],
                backgroundColor: 'transparent',
                borderWidth: 1.5,
                tension: 0.3,
                fill: false,
                hidden: i >= 4  // Hide cores 4+ by default
            }});
        }}
        new Chart(document.getElementById('cpuPerCoreFreqChart'), {{
            type: 'line',
            data: {{
                labels: chartData.timestamps,
                datasets: freqDatasets
            }},
            options: {{
                ...commonOptions,
                scales: {{
                    ...commonOptions.scales,
                    y: {{
                        ...commonOptions.scales.y,
                        title: {{ display: true, text: 'Frequency (MHz)', color: '#e0e0e0' }}
                    }}
                }}
            }}
        }});
        
        // CPU Temperature Chart
        const tempDatasets = [];
        const tempColors = ['#ff6348', '#ff9ff3', '#feca57', '#48dbfb', '#1dd1a1', '#10ac84'];
        for (let i = 0; i < chartData.cpu.max_temp_sensors; i++) {{
            const sensorLabel = chartData.cpu.temps[0] && chartData.cpu.temps[0][i] ? chartData.cpu.temps[0][i].label : `Sensor ${{i}}`;
            // Keep Package id visible, hide individual cores by default
            const isPackage = sensorLabel.toLowerCase().includes('package');
            tempDatasets.push({{
                label: sensorLabel,
                data: chartData.cpu.temps.map(sensors => sensors[i] ? sensors[i].current : 0),
                borderColor: tempColors[i % tempColors.length],
                backgroundColor: 'transparent',
                borderWidth: isPackage ? 2.5 : 1.5,  // Thicker line for package temp
                tension: 0.3,
                fill: false,
                hidden: !isPackage  // Hide individual core temps by default, show package
            }});
        }}
        new Chart(document.getElementById('cpuTempChart'), {{
            type: 'line',
            data: {{
                labels: chartData.timestamps,
                datasets: tempDatasets
            }},
            options: {{
                ...commonOptions,
                scales: {{
                    ...commonOptions.scales,
                    y: {{
                        ...commonOptions.scales.y,
                        title: {{ display: true, text: 'Temperature (°C)', color: '#e0e0e0' }}
                    }}
                }}
            }}
        }});
        
        // GPU Usage & Frequency Chart (Dual Y-axis)
        new Chart(document.getElementById('gpuUsageChart'), {{
            type: 'line',
            data: {{
                labels: chartData.timestamps,
                datasets: [{{
                    label: 'GPU Usage (%)',
                    data: chartData.gpu.usage,
                    borderColor: '#4ecdc4',
                    backgroundColor: 'rgba(78, 205, 196, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true,
                    yAxisID: 'y'
                }}, {{
                    label: 'GPU Frequency (MHz)',
                    data: chartData.gpu.freq,
                    borderColor: '#ffd93d',
                    backgroundColor: 'rgba(255, 217, 61, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: false,
                    yAxisID: 'y1'
                }}]
            }},
            options: {{
                ...commonOptions,
                scales: {{
                    ...commonOptions.scales,
                    y: {{
                        ...commonOptions.scales.y,
                        type: 'linear',
                        position: 'left',
                        title: {{ display: true, text: 'Usage (%)', color: '#4ecdc4' }},
                        min: 0,
                        max: 100
                    }},
                    y1: {{
                        type: 'linear',
                        position: 'right',
                        title: {{ display: true, text: 'Frequency (MHz)', color: '#ffd93d' }},
                        ticks: {{ color: '#888' }},
                        grid: {{ 
                            drawOnChartArea: false,
                            color: '#3a3a3a'
                        }}
                    }}
                }}
            }}
        }});
        
        // GPU Memory Chart
        new Chart(document.getElementById('gpuMemoryChart'), {{
            type: 'line',
            data: {{
                labels: chartData.timestamps,
                datasets: [{{
                    label: 'GPU Memory Used',
                    data: chartData.gpu.memory_used,
                    borderColor: '#4ecdc4',
                    backgroundColor: 'rgba(78, 205, 196, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true
                }}, {{
                    label: 'GPU Memory Utilization',
                    data: chartData.gpu.memory_util,
                    borderColor: '#ff6b6b',
                    backgroundColor: 'rgba(255, 107, 107, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true,
                    yAxisID: 'y1'
                }}]
            }},
            options: {{
                ...commonOptions,
                scales: {{
                    ...commonOptions.scales,
                    y: {{
                        ...commonOptions.scales.y,
                        title: {{ display: true, text: 'Memory (MB)', color: '#e0e0e0' }},
                        position: 'left'
                    }},
                    y1: {{
                        ...commonOptions.scales.y,
                        title: {{ display: true, text: 'Utilization (%)', color: '#e0e0e0' }},
                        position: 'right',
                        min: 0,
                        max: 100,
                        grid: {{ drawOnChartArea: false }}
                    }}
                }}
            }}
        }});
        
        // GPU Temperature Chart
        if (chartData.gpu.temp && chartData.gpu.temp.some(t => t > 0)) {{
            new Chart(document.getElementById('gpuTempChart'), {{
                type: 'line',
                data: {{
                    labels: chartData.timestamps,
                    datasets: [{{
                        label: 'GPU Temperature',
                        data: chartData.gpu.temp,
                        borderColor: '#ff6348',
                        backgroundColor: 'rgba(255, 99, 72, 0.1)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true
                    }}]
                }},
                options: {{
                    ...commonOptions,
                    scales: {{
                        ...commonOptions.scales,
                        y: {{
                            ...commonOptions.scales.y,
                            title: {{ display: true, text: 'Temperature (°C)', color: '#e0e0e0' }}
                        }}
                    }}
                }}
            }});
        }}
        
        // GPU Power Chart
        if (chartData.gpu.power && chartData.gpu.power.some(p => p > 0)) {{
            new Chart(document.getElementById('gpuPowerChart'), {{
                type: 'line',
                data: {{
                    labels: chartData.timestamps,
                    datasets: [{{
                        label: 'GPU Power',
                        data: chartData.gpu.power,
                        borderColor: '#feca57',
                        backgroundColor: 'rgba(254, 202, 87, 0.1)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true
                    }}]
                }},
                options: {{
                    ...commonOptions,
                    scales: {{
                        ...commonOptions.scales,
                        y: {{
                            ...commonOptions.scales.y,
                            title: {{ display: true, text: 'Power (W)', color: '#e0e0e0' }}
                        }}
                    }}
                }}
            }});
        }}
        
        // Memory Usage Chart
        new Chart(document.getElementById('memoryChart'), {{
            type: 'line',
            data: {{
                labels: chartData.timestamps,
                datasets: [{{
                    label: 'Memory Usage %',
                    data: chartData.memory.percent,
                    borderColor: '#a8e6cf',
                    backgroundColor: 'rgba(168, 230, 207, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true
                }}]
            }},
            options: {{
                ...commonOptions,
                scales: {{
                    ...commonOptions.scales,
                    y: {{
                        ...commonOptions.scales.y,
                        title: {{ display: true, text: 'Usage (%)', color: '#e0e0e0' }},
                        min: 0,
                        max: 100
                    }}
                }}
            }}
        }});
        
        // Memory Details Chart (Used/Available)
        new Chart(document.getElementById('memoryDetailsChart'), {{
            type: 'line',
            data: {{
                labels: chartData.timestamps,
                datasets: [{{
                    label: 'Memory Used',
                    data: chartData.memory.used,
                    borderColor: '#ff6b6b',
                    backgroundColor: 'rgba(255, 107, 107, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true
                }}, {{
                    label: 'Memory Available',
                    data: chartData.memory.available,
                    borderColor: '#4ecdc4',
                    backgroundColor: 'rgba(78, 205, 196, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true
                }}]
            }},
            options: {{
                ...commonOptions,
                scales: {{
                    ...commonOptions.scales,
                    y: {{
                        ...commonOptions.scales.y,
                        title: {{ display: true, text: 'Memory (GB)', color: '#e0e0e0' }}
                    }}
                }}
            }}
        }});
        
        // Swap Usage Chart
        if (chartData.memory.swap_percent && chartData.memory.swap_percent.some(s => s > 0)) {{
            new Chart(document.getElementById('swapChart'), {{
                type: 'line',
                data: {{
                    labels: chartData.timestamps,
                    datasets: [{{
                        label: 'Swap Usage',
                        data: chartData.memory.swap_percent,
                        borderColor: '#c589e8',
                        backgroundColor: 'rgba(197, 137, 232, 0.1)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true
                    }}]
                }},
                options: {{
                    ...commonOptions,
                    scales: {{
                        ...commonOptions.scales,
                        y: {{
                            ...commonOptions.scales.y,
                            title: {{ display: true, text: 'Usage (%)', color: '#e0e0e0' }},
                            min: 0,
                            max: 100
                        }}
                    }}
                }}
            }});
        }}
        
        // NPU Usage Chart (if available)
        if (chartData.npu && chartData.npu.usage && chartData.npu.usage.some(u => u > 0)) {{
            new Chart(document.getElementById('npuUsageChart'), {{
                type: 'line',
                data: {{
                    labels: chartData.timestamps,
                    datasets: [{{
                        label: 'NPU Usage',
                        data: chartData.npu.usage,
                        borderColor: '#c589e8',
                        backgroundColor: 'rgba(197, 137, 232, 0.1)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true
                    }}]
                }},
                options: {{
                    ...commonOptions,
                    scales: {{
                        ...commonOptions.scales,
                        y: {{
                            ...commonOptions.scales.y,
                            title: {{ display: true, text: 'Usage (%)', color: '#e0e0e0' }},
                            min: 0,
                            max: 100
                        }}
                    }}
                }}
            }});
        }}
        
        // Add double-click to reset zoom for all charts
        document.querySelectorAll('canvas').forEach(canvas => {{
            canvas.addEventListener('dblclick', function() {{
                const chart = Chart.getChart(canvas);
                if (chart && chart.resetZoom) {{
                    chart.resetZoom();
                }}
            }});
        }});
    </script>
</body>
</html>
"""
        
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
