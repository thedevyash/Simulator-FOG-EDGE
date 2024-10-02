import logging
import random
import simpy
from flask import Flask, render_template, request, redirect, url_for
import matplotlib.pyplot as plt
import io
import base64

from leaf.application import Application, SourceTask, ProcessingTask, SinkTask
from leaf.infrastructure import Node, Link, Infrastructure
from leaf.orchestrator import Orchestrator
from leaf.power import PowerModelNode, PowerModelLink, PowerMeter

RANDOM_SEED = 1

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s\t%(message)s')

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/step2', methods=['POST'])
def step2():
    sensor_count = int(request.form['sensor_count'])
    fog_count = int(request.form['fog_count'])
    edge_count = int(request.form['edge_count'])
    return render_template('step2.html', sensor_count=sensor_count, fog_count=fog_count, edge_count=edge_count)

@app.route('/simulate', methods=['POST'])
def simulate():
    sensor_count = int(request.form['sensor_count'])
    fog_count = int(request.form['fog_count'])
    edge_count = int(request.form['edge_count'])
    show_details = 'show_details' in request.form

    sensors = []
    fogs = []
    edges = []

    for i in range(sensor_count):
        sensors.append({
            'cu': float(request.form[f'sensor_cu_{i}']),
            'max_power': float(request.form[f'sensor_max_power_{i}']),
            'static_power': float(request.form[f'sensor_static_power_{i}'])
        })

    for i in range(fog_count):
        fogs.append({
            'cu': float(request.form[f'fog_cu_{i}']),
            'max_power': float(request.form[f'fog_max_power_{i}']),
            'static_power': float(request.form[f'fog_static_power_{i}'])
        })

    for i in range(edge_count):
        edges.append({
            'latency': float(request.form[f'edge_latency_{i}']),
            'bandwidth': float(request.form[f'edge_bandwidth_{i}']),
            'power_per_bit': float(request.form[f'edge_power_per_bit_{i}'])
        })

    cloud_power_per_cu = float(request.form['cloud_power_per_cu'])

    # Create infrastructure and application based on user input
    infrastructure = create_infrastructure(sensors, fogs, edges, cloud_power_per_cu)
    application = create_application(infrastructure)
    orchestrator = SimpleOrchestrator(infrastructure)
    orchestrator.place(application)

    application_pm = PowerMeter(application, name="application_meter")
    cloud_and_fog_pm = PowerMeter([infrastructure.node("cloud"), infrastructure.node("fog_0")], name="cloud_and_fog_meter")
    infrastructure_pm = PowerMeter(infrastructure, name="infrastructure_meter", measurement_interval=2)

    env = simpy.Environment()
    env.process(application_pm.run(env, delay=0.5))
    env.process(cloud_and_fog_pm.run(env))
    env.process(infrastructure_pm.run(env))
    env.run(until=5)

    # Generate a graph
    plt.figure()
    plt.plot([1, 2, 3], [4, 5, 6], label='Power Consumption')  # Example graph
    plt.xlabel('Time')
    plt.ylabel('Value')
    plt.title('Simulation Results')
    plt.legend()
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    graph_url = base64.b64encode(img.getvalue()).decode()

    # Collect additional details
    details = {
        'application_meter': application_pm.measurements,
        'cloud_and_fog_meter': cloud_and_fog_pm.measurements,
        'infrastructure_meter': infrastructure_pm.measurements,
    }

    return render_template('result.html', graph_url=graph_url, show_details=show_details, details=details)

def create_infrastructure(sensors, fogs, edges, cloud_power_per_cu):
    infrastructure = Infrastructure()
    sensor_nodes = []
    fog_nodes = []

    for i, sensor in enumerate(sensors):
        sensor_node = Node(f"sensor_{i}", cu=sensor['cu'], power_model=PowerModelNode(max_power=sensor['max_power'], static_power=sensor['static_power']))
        sensor_nodes.append(sensor_node)
        infrastructure.add_node(sensor_node)

    for i, fog in enumerate(fogs):
        fog_node = Node(f"fog_{i}", cu=fog['cu'], power_model=PowerModelNode(max_power=fog['max_power'], static_power=fog['static_power']))
        fog_nodes.append(fog_node)
        infrastructure.add_node(fog_node)

    cloud = Node("cloud", power_model=PowerModelNode(power_per_cu=cloud_power_per_cu))
    infrastructure.add_node(cloud)

    for i, edge in enumerate(edges):
        link = Link(sensor_nodes[i % len(sensor_nodes)], fog_nodes[i % len(fog_nodes)], latency=edge['latency'], bandwidth=edge['bandwidth'], power_model=PowerModelLink(edge['power_per_bit']))
        infrastructure.add_link(link)

    # Add a direct link between the first fog node and the cloud node
    if fog_nodes:
        direct_link = Link(fog_nodes[0], cloud, latency=edges[0]['latency'], bandwidth=edges[0]['bandwidth'], power_model=PowerModelLink(edges[0]['power_per_bit']))
        infrastructure.add_link(direct_link)

    return infrastructure

def create_application(infrastructure):
    application = Application()

    source_node = infrastructure.node("sensor_0")
    sink_node = infrastructure.node("cloud")

    source_task = SourceTask(cu=0.1, bound_node=source_node)
    processing_task = ProcessingTask(cu=5)
    sink_task = SinkTask(cu=0.5, bound_node=sink_node)

    application.add_task(source_task)
    application.add_task(processing_task, incoming_data_flows=[(source_task, 1000)])
    application.add_task(sink_task, incoming_data_flows=[(processing_task, 200)])

    return application

class SimpleOrchestrator(Orchestrator):
    def _processing_task_placement(self, processing_task: ProcessingTask, application: Application) -> Node:
        return self.infrastructure.node("fog_0")

if __name__ == '__main__':
    random.seed(RANDOM_SEED)
    app.run(debug=True)