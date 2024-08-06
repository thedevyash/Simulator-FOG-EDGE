import simpy
import matplotlib.pyplot as plt
from leaf.application import Task
from leaf.infrastructure import Node
from leaf.power import PowerModelNode

# Processes modify the model during the simulation
def place_task_after_2_seconds(env, node, task):
    """Waits for 2 seconds and places a task on a node."""
    yield env.timeout(2)
    task.allocate(node)

class RecordingPowerMeter:
    def __init__(self, node, callback=None):
        self.node = node
        self.callback = callback
        self.times = []
        self.powers = []

    def calculate_power(self):
        if self.node.cu == 0:
            return self.node.power_model.static_power
        else:
            return self.node.power_model.static_power + (self.node.cu / self.node.max_cu) * (self.node.power_model.max_power - self.node.power_model.static_power)

    def run(self, env):
        while True:
            power = self.calculate_power()  # Measure power based on node's cu
            self.times.append(env.now)
            self.powers.append(power)
            if self.callback:
                self.callback(power)
            yield env.timeout(1)

node = Node("node1", cu=0, power_model=PowerModelNode(max_power=30, static_power=10))
task = Task(cu=100)
recording_power_meter = RecordingPowerMeter(node, callback=lambda m: print(f"{env.now}: Node consumes {int(m)}W"))

env = simpy.Environment()  
# register our task placement process
env.process(place_task_after_2_seconds(env, node, task))
# register power metering process
env.process(recording_power_meter.run(env))
env.run(until=5)  

# Plotting the graph
plt.plot(recording_power_meter.times, recording_power_meter.powers, marker='o')
plt.xlabel('Time (seconds)')
plt.ylabel('Power Consumption (W)')
plt.title('Power Consumption Over Time')
plt.grid(True)
plt.show()
