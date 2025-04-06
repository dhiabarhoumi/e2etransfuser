import carla
client = carla.Client('localhost', 2000)
client.set_timeout(10.0)

tm = client.get_trafficmanager(8100)
print("Traffic Manager created:", tm)