from flask import Flask, request, jsonify, render_template
import simpy
import matplotlib.pyplot as plt
import io
import base64
from leaf.application import Task
from leaf.infrastructure import Node
from leaf.power import PowerModelNode, PowerMeter

class RecordingPowerMeter(PowerMeter):
    def __init__(self, node, callback=None):
        super().__init__(node, callback)
        self.times = []
        self.powers = []
        self.node = node  # Store the node as an instance attribute

    def run(self, env):
        while True:
            power = self.node.power_model.get_power(self.node.cu)
            self.times.append(env.now)
            self.powers.append(power)
            if self.callback:
                self.callback(power)
            yield env.timeout(1)

app = Flask(__name__)

def run_simulation(node_cu, max_power, static_power, task_cu):
    node = Node("node1", cu=node_cu, power_model=PowerModelNode(max_power=max_power, static_power=static_power))
    task = Task(cu=task_cu)
    power_meter = RecordingPowerMeter(node, callback=lambda m: print(f"{env.now}: Node consumes {int(m)}W"))

    env = simpy.Environment()
    env.process(place_task_after_2_seconds(env, node, task))
    env.process(power_meter.run(env))
    env.run(until=5)
    
    return power_meter.times, power_meter.powers

def place_task_after_2_seconds(env, node, task):
    """Waits for 2 seconds and places a task on a node."""
    yield env.timeout(2)
    task.allocate(node)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/simulate', methods=['POST'])
def simulate():
    node_cu = int(request.form['node_cu'])
    max_power = int(request.form['max_power'])
    static_power = int(request.form['static_power'])
    task_cu = int(request.form['task_cu'])
    
    times, powers = run_simulation(node_cu, max_power, static_power, task_cu)

    # Plotting the graph
    plt.figure()
    plt.plot(times, powers, marker='o')
    plt.xlabel('Time (seconds)')
    plt.ylabel('Power Consumption (W)')
    plt.title('Power Consumption Over Time')
    plt.grid(True)

    # Save it to a temporary buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    # Encode it to base64
    plot_url = base64.b64encode(buf.getvalue()).decode('utf8')
    plt.close()

    return jsonify({'plot_url': plot_url})

if __name__ == '__main__':
    app.run(debug=True)
