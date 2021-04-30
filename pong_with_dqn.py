# -*- coding: utf-8 -*-
"""pong with dqn

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/10gECtRW10KdXgIEzGlfWPukUr-ydqi7P
"""

import torch
import gym
import collections
import matplotlib.pyplot as plt
import cv2
import os
import torch as T
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np
checkpoint_file = "/content/sample_data/models"

class RepeatActionAndMaxFrame(gym.Wrapper):
    def __init__(self, env=None, repeat=4, clip_reward=False):
        super(RepeatActionAndMaxFrame, self).__init__(env)
        self.repeat = repeat
        self.shape = env.observation_space.low.shape
        self.frame_buffer = np.zeros_like((2, self.shape))
        self.clip_reward = clip_reward

    def step(self, action):
        t_reward = 0.0
        done = False
        for i in range(self.repeat):
            obs, reward, done, info = self.env.step(action)
            if self.clip_reward:
                reward = np.clip(np.array([reward]), -1, 1)[0]
            t_reward += reward
            idx = i % 2
            self.frame_buffer[idx] = obs
            if done:
                break

        max_frame = np.maximum(self.frame_buffer[0], self.frame_buffer[1])
        return max_frame, t_reward, done, info

    def reset(self):
        obs = self.env.reset()


        self.frame_buffer = np.zeros_like((2,self.shape))
        self.frame_buffer[0] = obs

        return obs

class RepeatActionMax(gym.Wrapper):
  def __init__(self, repeat, env = None, clip_reward = False):
    super(RepeatActionMax, self).__init__(env)
    self.repeat = repeat
    self.shape = env.observation_space.low.shape
    self.max_frame = np.zeros_like((2, max_frame))
    self.clip_reward = self.clip_reward
  def step(self, action):
    t_reward = 0
    done = False
    for i in range(self.repeat):
      obs, reward, done , info = self.env.step()
      if self.clip_reward:
        reward = np.clip([reward], -1, 1)[0]
      t_reward += reward
      idx = i%2
      self.max_frame[idx] = obs
      if done:
        break
    maxframe = max(self.max_frame[0], self.max_frame[1])

    return maxframe, t_reward, done , info

  def reset(self):
    obs = self.env.step()
    self.max_frame = np.zeros_like((2, self.shape))
    self.max_frame[0] = obs

    return obs

class PreprocessFrame(gym.ObservationWrapper):
  def __init__(self,shape, env = None):
    super(PreprocessFrame, self).__init__(env)
    self.shape = (shape[2], shape[0], shape[1])
    self.observation_space = gym.spaces.Box(low = 0.0, high = 1.0, shape = self.shape, dtype = np.float32)

  def observation(self, obs):
    new_frame = cv2.cvtColor(obs, cv2.COLOR_RGB2GRAY)
    resized_screen = cv2.resize(new_frame, self.shape[1:],
                                    interpolation=cv2.INTER_AREA)
    new_obs = np.array(resized_screen, dtype=np.uint8).reshape(self.shape)
    new_obs = new_obs / 255.0
    
    return new_obs

class StackFrames(gym.ObservationWrapper):
    def __init__(self, env, repeat):
        super(StackFrames, self).__init__(env)
        self.observation_space = gym.spaces.Box(
                            env.observation_space.low.repeat(repeat, axis=0),
                            env.observation_space.high.repeat(repeat, axis=0),
                            dtype=np.float32)
        self.stack = collections.deque(maxlen=repeat)

    def reset(self):
        self.stack.clear()
        #print("Noo")
        observation = self.env.reset()
        #print(observation.shape)
        for _ in range(self.stack.maxlen):
            self.stack.append(observation)

        return np.array(self.stack).reshape(self.observation_space.low.shape)

    def observation(self, observation):
        self.stack.append(observation)

        return np.array(self.stack).reshape(self.observation_space.low.shape)

def make_env(env_name, shape=(84,84,1), repeat=4, clip_rewards=False,
             no_ops=0, fire_first=False):
    env = gym.make(env_name)
    env = RepeatActionAndMaxFrame(env, repeat, clip_rewards)
    env = PreprocessFrame(shape, env)
    env = StackFrames(env, repeat)

    return env

class DeepQNetwork(nn.Module):
  def __init__(self, lr, n_actions ,name, input_dims):
    super(DeepQNetwork, self).__init__()
    self.lr = lr
    self.conv1 = nn.Conv2d(input_dims[0], 32, 8, stride=4)
    self.conv2 = nn.Conv2d(32, 64, 4, stride=2)
    self.conv3 = nn.Conv2d(64, 64, 3, stride=1)

    flatten = self.calculate_dims(input_dims)

    self.fc1 = nn.Linear(flatten, 512)
    self.fc2 = nn.Linear(512, n_actions)
    self.optimizer = optim.Adam(self.parameters(), lr = lr)
    self.loss = nn.MSELoss()
    self.device = T.device('cuda:0' if T.cuda.is_available() else 'cpu')
    self.to(self.device)


  def calculate_dims(self, input_dims):
    state = T.zeros(1, *input_dims)
    dims = self.conv1(state)
    dims = self.conv2(dims)
    dims = self.conv3(dims)

    return int(np.prod(dims.size()))

  def forward(self, state):
    layer1 = F.relu(self.conv1(state))
    layer2 = F.relu(self.conv2(layer1))
    layer3 = F.relu(self.conv3(layer2))
    conv_state = layer3.view(layer3.size()[0], -1)
    flat_1 = F.relu(self.fc1(conv_state))
    actions = self.fc2(flat_1)

    return actions

class Agent():
  def __init__(self, gamma, epsilon , lr, n_actions,input_dims,mem_size , batch_size,eps_min = 0.01,eps_dec = 5e-7,
                env_name = None):
    self.lr = lr
    self.epsilon = epsilon
    self.gamma = gamma
    self.eps_dec = eps_dec
    self.mem_size = mem_size
    self.eps_min = eps_min
    self.input_dims = input_dims
    self.env_name = env_name 
    self.batch_size = batch_size
    self.n_actions = n_actions
    self.action_space = [i for i in range(n_actions)]
    self.mem_cntr = 0
    self.state_memory = np.zeros((self.mem_size, *input_dims), dtype = np.float32)
    self.new_state_memory = np.zeros((self.mem_size, *input_dims), dtype = np.float32)
    self.action_memory = np.zeros(self.mem_size, dtype = np.int32)
    self.reward_memory = np.zeros(self.mem_size, dtype = np.float32)
    self.terminal_memory = np.zeros(self.mem_size, dtype = np.bool)

    self.q_eval = DeepQNetwork(self.lr, self.n_actions,
                                    input_dims=self.input_dims,
                                    name=self.env_name)

    self.q_next = DeepQNetwork(self.lr, self.n_actions,
                                    input_dims=self.input_dims,
                                    name=self.env_name)


  def store_transition(self,state, action, reward, state_, done):
        index = self.mem_cntr % self.mem_size
        #print(index)
        self.state_memory[index] = state
        self.new_state_memory[index] = state_
        self.reward_memory[index] = reward
        self.action_memory[index] = action
        self.terminal_memory[index] = done
        self.mem_cntr += 1
        self.step_counter = 0

  def choose_actions(self ,observation):
        if np.random.random() > self.epsilon:
            state = T.tensor([observation],dtype= T.float32).to(self.q_eval.device)
            
            actions = self.q_eval.forward(state)
            action = T.argmax(actions).item()
        else:
            action = np.random.choice(self.action_space) 

        return action
  def learn(self):
       if self.mem_cntr < self.batch_size:
         return
       self.q_eval.optimizer.zero_grad()

       if self.step_counter % 1000 == 0:
            self.q_next.load_state_dict(self.q_eval.state_dict())

       max_mem = min(self.mem_cntr, self.mem_size)
       batch = np.random.choice(max_mem, self.batch_size, replace=False)
       batch_index = np.arange(self.batch_size, dtype = np.int32)
       state_batch = T.tensor(self.state_memory[batch]).to(self.q_eval.device)
       new_state_batch = T.tensor(self.new_state_memory[batch]).to(self.q_eval.device)
       reward_batch = T.tensor(self.reward_memory[batch]).to(self.q_eval.device)
       terminal_batch = T.tensor(self.terminal_memory[batch]).to(self.q_eval.device)
       action_batch = self.action_memory[batch]

       q_eval = self.q_eval.forward(state_batch)[batch_index, action_batch]
       q_next = self.q_next.forward(new_state_batch)
       q_next[terminal_batch] = 0.0

       q_target = reward_batch + self.gamma * T.max(q_next, dim = 1)[0]

       loss = self.q_eval.loss(q_target,q_eval).to(self.q_eval.device)
       loss.backward()
       self.q_eval.optimizer.step()
       self.step_counter += 1

       self.epsilon  = self.epsilon - self.eps_dec if self.epsilon > self.eps_min \
                        else self.eps_min

def plot_learning_curve(x, scores, epsilons, filename, lines=None):
    fig=plt.figure()
    ax=fig.add_subplot(111, label="1")
    ax2=fig.add_subplot(111, label="2", frame_on=False)

    ax.plot(x, epsilons, color="C0")
    ax.set_xlabel("Training Steps", color="C0")
    ax.set_ylabel("Epsilon", color="C0")
    ax.tick_params(axis='x', colors="C0")
    ax.tick_params(axis='y', colors="C0")

    N = len(scores)
    running_avg = np.empty(N)
    for t in range(N):
	    running_avg[t] = np.mean(scores[max(0, t-20):(t+1)])

    ax2.scatter(x, running_avg, color="C1")
    ax2.axes.get_xaxis().set_visible(False)
    ax2.yaxis.tick_right()
    ax2.set_ylabel('Score', color="C1")
    ax2.yaxis.set_label_position('right')
    ax2.tick_params(axis='y', colors="C1")

    if lines is not None:
        for line in lines:
            plt.axvline(x=line)

    plt.savefig(filename)

env = make_env('PongNoFrameskip-v4')
best_score = -np.inf
load_checkpoint = False
n_epsiodes = 500

agent = Agent(gamma=0.99, epsilon=1, lr=0.0001,
                     input_dims=(env.observation_space.shape),
                     n_actions=env.action_space.n, mem_size=20000, eps_min=0.1,
                     batch_size=32, eps_dec=1e-5,env_name = 'Pong' )

n_steps = 0
scores, eps_history, steps_array = [], [], []
load_checkpoint = False
for i in range(n_epsiodes):
  done = False
  observation = env.reset()
  #print(observation.shape)
  score = 0
  while not done:

    #print(observation.shape)
    action = agent.choose_actions(observation)
    observation_, reward, done, info = env.step(action)
    #print(observation_.shape)
    score += reward
    if not load_checkpoint:
      agent.store_transition(observation, action,
                                     reward, observation_, done)
      agent.learn()
    observation = observation_
    n_steps += 1
  scores.append(score)
  steps_array.append(n_steps)
  avg_score = np.mean(scores[-100:])
  print('episode: ', i,'score: ', score,
             ' average score %.1f' % avg_score, 'best score %.2f' % best_score,
            'epsilon %.2f' % agent.epsilon, 'steps', n_steps)
  
  if avg_score > best_score:
    best_score = avg_score

figure_file = 'pong'+'.png'
  x = [i+1 for i in range(len(scores))]
  plot_learning_curve(steps_array, scores, eps_history, figure_file)

agent.q_eval.state_dict()

