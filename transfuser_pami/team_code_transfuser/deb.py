import os

data_root = "/media/ros/hdd2/Porjects/e2etransfuser/transfuser_pami/data/coke_dataset_23_11"  # Change this to your actual dataset path

total_lidar_files = 0

for scenario in os.listdir(data_root):
    scenario_path = os.path.join(data_root, scenario)
    if not os.path.isdir(scenario_path):
        continue

    for route in os.listdir(scenario_path):
        route_path = os.path.join(scenario_path, route)
        lidar_path = os.path.join(route_path, "lidar")

        if os.path.exists(lidar_path) and os.path.isdir(lidar_path):
            lidar_files = [f for f in os.listdir(lidar_path) if f.endswith('.npy')]
            print(f"🟢 {scenario}/{route} → {len(lidar_files)} files found")
            total_lidar_files += len(lidar_files)
        else:
            print(f"⚠️ {scenario}/{route} → No 'lidar' folder found")

print(f"\nTotal LiDAR files found: {total_lidar_files}")
