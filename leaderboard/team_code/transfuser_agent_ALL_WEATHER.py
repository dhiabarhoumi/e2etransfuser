import os
import json
import datetime
import pathlib
import time
import cv2
import carla
from collections import deque

import torch
import carla
import numpy as np
from PIL import Image

from leaderboard.autoagents import autonomous_agent
from transfuser.model import TransFuser
from transfuser.config import GlobalConfig
from transfuser.data import scale_and_crop_image, lidar_to_histogram_features, transform_2d_points
from team_code.planner import RoutePlanner

import math
from matplotlib import cm
from srunner.scenariomanager.carla_data_provider import CarlaDataProvider
import random

SAVE_PATH = os.environ.get('SAVE_PATH', None)


def get_entry_point():
	return 'TransFuserAgent'


class TransFuserAgent(autonomous_agent.AutonomousAgent):
	def setup(self, path_to_conf_file):
		self.lidar_processed = list()
		self.track = autonomous_agent.Track.SENSORS
		self.config_path = path_to_conf_file
		self.step = -1
		self.wall_start = time.time()
		self.initialized = False

		self.input_buffer = {'rgb': deque(), 'rgb_left': deque(), 'rgb_right': deque(), 
							'rgb_rear': deque(), 'lidar': deque(), 'gps': deque(), 'thetas': deque()}

		self.config = GlobalConfig()
		self.net = TransFuser(self.config, 'cuda')
		self.net.load_state_dict(torch.load(os.path.join(path_to_conf_file, 'best_model.pth')))
		self.net.cuda()
		self.net.eval()

		self.weathers = {
            'Clear': carla.WeatherParameters.ClearNoon,
            'Cloudy': carla.WeatherParameters.CloudySunset,
            'Wet': carla.WeatherParameters.WetSunset,
            'MidRain': carla.WeatherParameters.MidRainSunset,
            'WetCloudy': carla.WeatherParameters.WetCloudySunset,
            'HardRain': carla.WeatherParameters.HardRainNoon,
            'SoftRain': carla.WeatherParameters.SoftRainSunset,
        }
		self.azimuths = [45.0 * i for i in range(8)]
		self.daytimes = {
            'Night': -80.0,
            'Twilight': 0.0,
            'Dawn': 5.0,
            'Sunset': 15.0,
            'Morning': 35.0,
            'Noon': 75.0,
        }
		
		self.weathers_ids = list(self.weathers)
#		self._vehicle = CarlaDataProvider.get_hero_actor()
#		self._world = self._vehicle.get_world()


		self.save_path = None
		if SAVE_PATH is not None:
			now = datetime.datetime.now()
			string = pathlib.Path(os.environ['ROUTES']).stem + '_'
			string += '_'.join(map(lambda x: '%02d' % x, (now.month, now.day, now.hour, now.minute, now.second)))

			print (string)

			self.save_path = pathlib.Path(os.environ['SAVE_PATH']) / string
			self.save_path.mkdir(parents=True, exist_ok=False)

			(self.save_path / 'rgb').mkdir(parents=True, exist_ok=False)
			(self.save_path / 'lidar_0').mkdir(parents=True, exist_ok=False)
			(self.save_path / 'lidar_1').mkdir(parents=True, exist_ok=False)
			(self.save_path / 'meta').mkdir(parents=True, exist_ok=False)

	def _init(self):
		self._route_planner = RoutePlanner(4.0, 50.0)
		self._route_planner.set_route(self._global_plan, True)
		self._world = CarlaDataProvider.get_world()
		self._vehicle_lights = carla.VehicleLightState.Position | carla.VehicleLightState.LowBeam

		self.initialized = True

	def _get_position(self, tick_data):
		gps = tick_data['gps']
		gps = (gps - self._route_planner.mean) * self._route_planner.scale

		return gps
	
	def scale_crop(self, image, scale=1, start_x=0, crop_x=None, start_y=0, crop_y=None):
		(width, height) = (image.width // scale, image.height // scale)
		if scale != 1:
			image = image.resize((width, height))
		if crop_x is None:
			crop_x = width
		if crop_y is None:
			crop_y = height

		image = np.asarray(image)
		cropped_image = image[start_y:start_y+crop_y, start_x:start_x+crop_x]
		return cropped_image
	

	def sensors(self):
		return [

			{
					'type': 'sensor.camera.rgb',
                    'x': 1.3, 'y': 0.0, 'z':self.config.camera_z,
					'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0,
					'width': self.config.camera_width, 'height': self.config.camera_height, 'fov': self.config.fov,
					'id': 'rgb_front'
					},
				{
			 	'type': 'sensor.camera.rgb',
				 	'x': 1.3, 'y': 0.0, 'z': self.config.camera_z,
				 	'roll': 0.0, 'pitch': 0.0, 'yaw': -60.0,
				 	'width': self.config.camera_width, 'height': self.config.camera_height, 'fov': self.config.fov,
				 	'id': 'rgb_left'
				 	},
				{
				 	'type': 'sensor.camera.rgb',
				 	'x': 1.3, 'y': 0.0, 'z':self.config.camera_z,
				 	'roll': 0.0, 'pitch': 0.0, 'yaw': 60.0,
				 	'width': self.config.camera_width, 'height': self.config.camera_height, 'fov': self.config.fov,
				 	'id': 'rgb_right'
				 	},
				# {
				# 	'type': 'sensor.camera.rgb',
				# 	'x': 1.3, 'y': 0.0, 'z':2.3,
				# 	'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0,
				# 	'width': 400, 'height': 300, 'fov': 100,
				# 	'id': 'rgb'
				# 	},
				# {
				# 	'type': 'sensor.camera.rgb',
				# 	'x': 1.3, 'y': 0.0, 'z':2.3,
				# 	'roll': 0.0, 'pitch': 0.0, 'yaw': -60.0,
				# 	'width': 400, 'height': 300, 'fov': 100,
				# 	'id': 'rgb_left'
				# 	},
				# {
				# 	'type': 'sensor.camera.rgb',
				# 	'x': 1.3, 'y': 0.0, 'z':2.3,
				# 	'roll': 0.0, 'pitch': 0.0, 'yaw': 60.0,
				# 	'width': 400, 'height': 300, 'fov': 100,
				# 	'id': 'rgb_right'
				# 	},
				# {
				# 	'type': 'sensor.camera.rgb',
				# 	'x': -1.3, 'y': 0.0, 'z':2.3,
				# 	'roll': 0.0, 'pitch': 0.0, 'yaw': -180.0,
				# 	'width': 400, 'height': 300, 'fov': 100,
				# 	'id': 'rgb_rear'
				# 	},
                {   
                    'type': 'sensor.lidar.ray_cast',
                    'x': 1.3, 'y': 0.0, 'z': 2.5,
                    'roll': 0.0, 'pitch': 0.0, 'yaw': -90.0,
                    'id': 'lidar'
                    },
				{
					'type': 'sensor.other.imu',
					'x': 0.0, 'y': 0.0, 'z': 0.0,
					'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0,
					'sensor_tick': 0.05,
					'id': 'imu'
					},
				{
					'type': 'sensor.other.gnss',
					'x': 0.0, 'y': 0.0, 'z': 0.0,
					'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0,
					'sensor_tick': 0.01,
					'id': 'gps'
					},
				{
					'type': 'sensor.speedometer',
					'reading_frequency': 20,
					'id': 'speed'
					}
				]

	def tick(self, input_data):
		self.step += 1
		rgb = []
		for pos in ['front']:  #TODO only 'front'  for 1 image,  [ 'left','front','right'] for 3 images
			rgb_cam = 'rgb_' + pos
			rgb_pos = cv2.cvtColor(input_data[rgb_cam][1][:, :, :3], cv2.COLOR_BGR2RGB)
			rgb_pos = self.scale_crop(Image.fromarray(rgb_pos), self.config.scale, self.config.img_width_cut, self.config.img_width_cut, self.config.img_resolution[0], self.config.img_resolution[0])
			rgb.append(rgb_pos)
		rgb = np.concatenate(rgb, axis=1)
	

#		rgb = cv2.cvtColor(input_data['rgb'][1][:, :, :3], cv2.COLOR_BGR2RGB)
#		rgb_left = cv2.cvtColor(input_data['rgb_left'][1][:, :, :3], cv2.COLOR_BGR2RGB)
#		rgb_right = cv2.cvtColor(input_data['rgb_right'][1][:, :, :3], cv2.COLOR_BGR2RGB)
#		rgb_rear = cv2.cvtColor(input_data['rgb_rear'][1][:, :, :3], cv2.COLOR_BGR2RGB)
		gps = input_data['gps'][1][:2]
		speed = input_data['speed'][1]['speed']
		compass = input_data['imu'][1][-1]
		if (math.isnan(compass) == True): #It can happen that the compass sends nan for a few frames
			compass = 0.0
		lidar = input_data['lidar'][1][:, :3]

		result = {
				'rgb': rgb,
				# 'rgb_left': rgb_left,
				# 'rgb_right': rgb_right,
				# 'rgb_rear': rgb_rear,
				'lidar': lidar,
				'gps': gps,
				'speed': speed,
				'compass': compass,
				}
		
		pos = self._get_position(result)
		result['gps'] = pos
		next_wp, next_cmd = self._route_planner.run_step(pos)
		result['next_command'] = next_cmd.value

		theta = compass + np.pi/2
		R = np.array([
			[np.cos(theta), -np.sin(theta)],
			[np.sin(theta), np.cos(theta)]
			])

		local_command_point = np.array([next_wp[0]-pos[0], next_wp[1]-pos[1]])
		local_command_point = R.T.dot(local_command_point)
		result['target_point'] = tuple(local_command_point)

		return result

	@torch.no_grad()
	def run_step(self, input_data, timestamp):
		if not self.initialized:
			self._init()

		tick_data = self.tick(input_data)
		if self.step < self.config.seq_len:
			rgb = torch.from_numpy(scale_and_crop_image(Image.fromarray(tick_data['rgb']), crop=self.config.input_resolution)).unsqueeze(0)
			self.input_buffer['rgb'].append(rgb.to('cuda', dtype=torch.float32))
			
			# if not self.config.ignore_sides:
			# 	rgb_left = torch.from_numpy(scale_and_crop_image(Image.fromarray(tick_data['rgb_left']), crop=self.config.input_resolution)).unsqueeze(0)
			# 	self.input_buffer['rgb_left'].append(rgb_left.to('cuda', dtype=torch.float32))
				
			# 	rgb_right = torch.from_numpy(scale_and_crop_image(Image.fromarray(tick_data['rgb_right']), crop=self.config.input_resolution)).unsqueeze(0)
			# 	self.input_buffer['rgb_right'].append(rgb_right.to('cuda', dtype=torch.float32))

			# if not self.config.ignore_rear:
			# 	rgb_rear = torch.from_numpy(scale_and_crop_image(Image.fromarray(tick_data['rgb_rear']), crop=self.config.input_resolution)).unsqueeze(0)
			# 	self.input_buffer['rgb_rear'].append(rgb_rear.to('cuda', dtype=torch.float32))

			self.input_buffer['lidar'].append(tick_data['lidar'])
			self.input_buffer['gps'].append(tick_data['gps'])
			self.input_buffer['thetas'].append(tick_data['compass'])

			control = carla.VehicleControl()
			control.steer = 0.0
			control.throttle = 0.0
			control.brake = 0.0
			
			return control
		
		gt_velocity = torch.FloatTensor([tick_data['speed']]).to('cuda', dtype=torch.float32)
		command = torch.FloatTensor([tick_data['next_command']]).to('cuda', dtype=torch.float32)

		tick_data['target_point'] = [torch.FloatTensor([tick_data['target_point'][0]]),
											torch.FloatTensor([tick_data['target_point'][1]])]
		target_point = torch.stack(tick_data['target_point'], dim=1).to('cuda', dtype=torch.float32)

		encoding = []
		rgb = torch.from_numpy(scale_and_crop_image(Image.fromarray(tick_data['rgb']), crop=self.config.input_resolution)).unsqueeze(0)
		self.input_buffer['rgb'].popleft()
		self.input_buffer['rgb'].append(rgb.to('cuda', dtype=torch.float32))
		
		# if not self.config.ignore_sides:
		# 	rgb_left = torch.from_numpy(scale_and_crop_image(Image.fromarray(tick_data['rgb_left']), crop=self.config.input_resolution)).unsqueeze(0)
		# 	self.input_buffer['rgb_left'].popleft()
		# 	self.input_buffer['rgb_left'].append(rgb_left.to('cuda', dtype=torch.float32))
			
		# 	rgb_right = torch.from_numpy(scale_and_crop_image(Image.fromarray(tick_data['rgb_right']), crop=self.config.input_resolution)).unsqueeze(0)
		# 	self.input_buffer['rgb_right'].popleft()
		# 	self.input_buffer['rgb_right'].append(rgb_right.to('cuda', dtype=torch.float32))

		# if not self.config.ignore_rear:
		# 	rgb_rear = torch.from_numpy(scale_and_crop_image(Image.fromarray(tick_data['rgb_rear']), crop=self.config.input_resolution)).unsqueeze(0)
		# 	self.input_buffer['rgb_rear'].popleft()
		# 	self.input_buffer['rgb_rear'].append(rgb_rear.to('cuda', dtype=torch.float32))

		self.input_buffer['lidar'].popleft()
		self.input_buffer['lidar'].append(tick_data['lidar'])
		self.input_buffer['gps'].popleft()
		self.input_buffer['gps'].append(tick_data['gps'])
		self.input_buffer['thetas'].popleft()
		self.input_buffer['thetas'].append(tick_data['compass'])

		# transform the lidar point clouds to local coordinate frame
		ego_theta = self.input_buffer['thetas'][-1]
		ego_x, ego_y = self.input_buffer['gps'][-1]

		#Only predict every second step because we only get a LiDAR every second frame.
		if(self.step  % 2 == 0 or self.step <= 4):
			self.lidar_processed = list() #ini harusnya di sini!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
			for i, lidar_point_cloud in enumerate(self.input_buffer['lidar']):
				curr_theta = self.input_buffer['thetas'][i]
				curr_x, curr_y = self.input_buffer['gps'][i]
				lidar_point_cloud[:,1] *= -1 # inverts x, y
				lidar_transformed = transform_2d_points(lidar_point_cloud,
						np.pi/2-curr_theta, -curr_x, -curr_y, np.pi/2-ego_theta, -ego_x, -ego_y)
				lidar_transformed = torch.from_numpy(lidar_to_histogram_features(lidar_transformed, crop=self.config.input_resolution)).unsqueeze(0)
				self.lidar_processed.append(lidar_transformed.to('cuda', dtype=torch.float32))


			#self.pred_wp = self.net(self.input_buffer['rgb'] + self.input_buffer['rgb_left'] + \
			#				   self.input_buffer['rgb_right']+self.input_buffer['rgb_rear'], \
			#				   self.lidar_processed, target_point, gt_velocity)
			self.pred_wp = self.net(self.input_buffer['rgb'], 
							   self.lidar_processed, target_point, gt_velocity)
		steer, throttle, brake, metadata = self.net.control_pid(self.pred_wp, gt_velocity)
		self.pid_metadata = metadata

		if brake < 0.05: brake = 0.0
		if throttle > brake: brake = 0.0

		control = carla.VehicleControl()
		control.steer = float(steer)
		control.throttle = float(throttle)
		control.brake = float(brake)

		if SAVE_PATH is not None and self.step % 10 == 0:
			self.save(tick_data)
			
		if self.step % 50 == 0:
			self.shuffle_weather()
			
		return control
		
	def shuffle_weather(self):
		# change weather for visual diversity
		index = random.choice(range(len(self.weathers)))
		dtime, altitude = random.choice(list(self.daytimes.items()))
		altitude = np.random.normal(altitude, 10)
		self.weather_id = self.weathers_ids[index] + dtime

		weather = self.weathers[self.weathers_ids[index]]
		weather.sun_altitude_angle = altitude
		weather.sun_azimuth_angle = np.random.choice(self.azimuths)
		self._world.set_weather(weather)

		# night mode
		vehicles = self._world.get_actors().filter('*vehicle*')
		if weather.sun_altitude_angle < 0.0:
			for vehicle in vehicles:
				vehicle.set_light_state(carla.VehicleLightState(self._vehicle_lights))
		else:
			for vehicle in vehicles:
				vehicle.set_light_state(carla.VehicleLightState.NONE)
		
		
	def save(self, tick_data):
		frame = self.step // 10

		Image.fromarray(tick_data['rgb']).save(self.save_path / 'rgb' / ('%04d.png' % frame))

		Image.fromarray(cm.gist_earth(self.lidar_processed[0].cpu().numpy()[0, 0], bytes=True)).save(self.save_path / 'lidar_0' / ('%04d.png' % frame))
		Image.fromarray(cm.gist_earth(self.lidar_processed[0].cpu().numpy()[0, 1], bytes=True)).save(self.save_path / 'lidar_1' / ('%04d.png' % frame))


		outfile = open(self.save_path / 'meta' / ('%04d.json' % frame), 'w')
		json.dump(self.pid_metadata, outfile, indent=4)
		outfile.close()

	def destroy(self):
		del self.net
