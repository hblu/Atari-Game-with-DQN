#!/usr/bin/env python
"""Run Atari Environment with DQN."""
import argparse
import os
import random

import numpy as np
import tensorflow as tf
from keras.layers import (Activation, Conv2D, Dense, Flatten, Input, Lambda)
from keras.models import model_from_json

from keras.models import Model

import deeprl_hw2 as tfrl
from deeprl_hw2.dqn import DQNAgent
from deeprl_hw2.objectives import mean_huber_loss
from deeprl_hw2.preprocessors import AtariPreprocessor
from deeprl_hw2.core import *
from deeprl_hw2.policy import *

import gym

import keras.backend as K


def create_model(window, input_shape, num_actions, model_name='deep_q_network', trainable=True):  # noqa: D103
    """Create the Deep-Q-network model.

    Use Keras to construct a keras.models.Model instance (you can also
    use the SequentialModel class).

    We highly recommend that you use tf.name_scope as discussed in
    class when creating the model and the layers. This will make it
    far easier to understnad your network architecture if you are
    logging with tensorboard.

    Parameters
    ----------
    window: int
      Each input to the network is a sequence of frames. This value
      defines how many frames are in the sequence.
    input_shape: tuple(int, int)
      The expected input image size.
    num_actions: int
      Number of possible actions. Defined by the gym environment.
    model_name: str
      Useful when debugging. Makes the model show up nicer in tensorboard.

    Returns
    -------
    keras.models.Model
      The Q-model.
    """

    input_shape = (input_shape[0], input_shape[1], window)
    state = Input(shape=input_shape)
    model = None

    if model_name == "deep_q_network":
        print "Building " + model_name + " ..."

        # First convolutional layer
        x = Conv2D(filters=16, kernel_size=(8, 8), strides=(4, 4), padding='valid', trainable=trainable)(state)
        x = Activation('relu')(x)
        # Second convolutional layer
        x = Conv2D(filters=32, kernel_size=(4, 4), strides=(2, 2), padding='valid', trainable=trainable)(x)
        x = Activation('relu')(x)
        # flatten the tensor
        x = Flatten()(x)
        x = Activation('relu')(x)
        x = Dense(256, trainable=trainable)(x)
        # x = Activation('relu')(x)
        # output layer
        y_pred = Dense(num_actions, trainable=trainable)(x)

        model = Model(input=state, output=y_pred)

    elif model_name == "deep_q_network_double":
        print "Building " + model_name + " ..."

        # First convolutional layer
        x = Conv2D(filters=32, kernel_size=(8, 8), strides=(4, 4), padding='valid', trainable=trainable)(state)
        x = Activation('relu')(x)
        # Second convolutional layer
        x = Conv2D(filters=64, kernel_size=(4, 4), strides=(2, 2), padding='valid', trainable=trainable)(x)
        x = Activation('relu')(x)
        # Third convolutional layer
        x = Conv2D(filters=64, kernel_size=(3, 3), strides=(1, 1), padding='valid', trainable=trainable)(x)
        x = Activation('relu')(x)
        # flatten the tensor
        x = Flatten()(x)
        x = Activation('relu')(x)
        x = Dense(512, trainable=trainable)(x)
        # x = Activation('relu')(x)
        # output layer
        y_pred = Dense(num_actions, trainable=trainable)(x)

        model = Model(input=state, output=y_pred)

    elif model_name == "deep_q_network_duel":
        print "Building " + model_name + " ..."

        # First convolutional layer
        x = Conv2D(filters=32, kernel_size=(8, 8), strides=(4, 4), padding='valid', trainable=trainable)(state)
        x = Activation('relu')(x)
        # Second convolutional layer
        x = Conv2D(filters=64, kernel_size=(4, 4), strides=(2, 2), padding='valid', trainable=trainable)(x)
        x = Activation('relu')(x)
        # Third convolutional layer
        x = Conv2D(filters=64, kernel_size=(3, 3), strides=(1, 1), padding='valid', trainable=trainable)(x)
        x = Activation('relu')(x)

        x = Flatten()(x)
        x = Activation('relu')(x)
        # value output
        x_val = Dense(512, trainable=trainable)(x)
        # x_val = Activation('relu')(x_val)
        y_val = Dense(1, trainable=trainable)(x_val)

        # advantage output
        x_advantage = Dense(512, trainable=trainable)(x)
        # x_advantage = Activation('relu')(x_advantage)
        y_advantage = Dense(num_actions, trainable=trainable)(x_advantage)
        # mean advantage
        y_advantage_mean = Lambda(lambda x: K.mean(x, axis=1, keepdims=True))(y_advantage)

        y_q = Lambda(lambda x: x[0] + x[1] - x[2])([y_val, y_advantage, y_advantage_mean])

        model = Model(input=state, output=y_q)

    elif model_name == "linear_q_network" or model_name == "linear_q_network_double":

        x = Flatten()(state)
        x = Dense(256, trainable=trainable)(x)
        y_pred = Dense(num_actions, trainable=trainable)(x)
        model = Model(output=y_pred, input=state)
    else:
        print "Model not supported"
        exit(1)

    return model


def get_output_folder(parent_dir, env_name):
    """Return save folder.

    Assumes folders in the parent_dir have suffix -run{run
    number}. Finds the highest run number and sets the output folder
    to that number + 1. This is just convenient so that if you run the
    same script multiple times tensorboard can plot all of the results
    on the same plots with different names.

    Parameters
    ----------
    parent_dir: str
      Path of the directory containing all experiment runs.

    Returns
    -------
    parent_dir/run_dir
      Path to this run's save directory.
    """
    os.makedirs(parent_dir, exist_ok=True)
    experiment_id = 0
    for folder_name in os.listdir(parent_dir):
        if not os.path.isdir(os.path.join(parent_dir, folder_name)):
            continue
        try:
            folder_name = int(folder_name.split('-run')[-1])
            if folder_name > experiment_id:
                experiment_id = folder_name
        except:
            pass
    experiment_id += 1

    parent_dir = os.path.join(parent_dir, env_name)
    parent_dir = parent_dir + '-run{}'.format(experiment_id) + '/'
    return parent_dir


def main():  # noqa: D103
    parser = argparse.ArgumentParser(description='Run DQN on Atari Breakout')
    parser.add_argument('--env', default='SpaceInvaders-v0', help='Atari env name')
    parser.add_argument('--network_name', default='linear_q_network', type=str, help='Type of model to use')
    parser.add_argument('--window', default=4, type=int, help='how many frames are used each time')
    parser.add_argument('--new_size', default=(84, 84), type=tuple, help='new size')
    parser.add_argument('--batch_size', default=32, type=int, help='Batch size')
    parser.add_argument('--replay_buffer_size', default=750000, type=int, help='Replay buffer size')
    parser.add_argument('--gamma', default=0.99, type=float, help='Discount factor')
    parser.add_argument('--alpha', default=0.0001, type=float, help='Learning rate')
    parser.add_argument('--epsilon', default=0.05, type=float, help='Exploration probability for epsilon-greedy')
    parser.add_argument('--target_update_freq', default=10000, type=int,
                        help='Frequency for copying weights to target network')
    parser.add_argument('--num_burn_in', default=50000, type=int,
                        help='Number of prefilled samples in the replay buffer')
    parser.add_argument('--num_iterations', default=5000000, type=int,
                        help='Number of overal interactions to the environment')
    parser.add_argument('--max_episode_length', default=200000, type=int, help='Terminate earlier for one episode')
    parser.add_argument('--train_freq', default=4, type=int, help='Frequency for training')
    parser.add_argument('--repetition_times', default=3, type=int, help='Parameter for action repetition')
    parser.add_argument('-o', '--output', default='atari-v0', type=str, help='Directory to save data to')
    parser.add_argument('--seed', default=0, type=int, help='Random seed')
    parser.add_argument('--experience_replay', default=False, type=bool,
                        help='Choose whether or not to use experience replay')
    parser.add_argument('--train', default=True, type=bool, help='Train/Evaluate, set True if train the model')
    parser.add_argument('--model_path', default='/media/hongbao/Study/Courses/10703/hw2/lqn_noexp',
                        type=str, help='specify model path to evaluation')
    parser.add_argument('--max_grad', default=1.0, type=float, help='Parameter for huber loss')
    parser.add_argument('--model_num', default=5000000, type=int, help='specify saved model number during train')
    parser.add_argument('--log_dir', default='log', type=str, help='specify log folder to save evaluate result')
    parser.add_argument('--eval_num', default=100, type=int, help='number of evaluation to run')
    parser.add_argument('--save_freq', default=100000, type=int, help='model save frequency')

    args = parser.parse_args()
    print("\nParameters:")
    for arg in vars(args):
        print arg, getattr(args, arg)
    print("")

    env = gym.make(args.env)
    num_actions = env.action_space.n
    # define model object
    preprocessor = AtariPreprocessor(args.new_size)
    memory = ReplayMemory(args.replay_buffer_size, args.window)

    # Initiating policy for both tasks (training and evaluating)
    policy = LinearDecayGreedyEpsilonPolicy(args.epsilon, 0, 1000000)

    if not args.train:
        '''Evaluate the model'''
        # check model path
        if args.model_path is '':
            print "Model path must be set when evaluate"
            exit(1)

        # specific log file to save result
        log_file = os.path.join(args.log_dir, args.network_name, str(args.model_num))
        model_dir = os.path.join(args.model_path, args.network_name, str(args.model_num))

        with tf.Session() as sess:
            # load model
            with open(model_dir + ".json", 'r') as json_file:
                loaded_model_json = json_file.read()
                q_network_online = model_from_json(loaded_model_json)
                q_network_target = model_from_json(loaded_model_json)

            sess.run(tf.global_variables_initializer())

            # load weights into model
            q_network_online.load_weights(model_dir + ".h5")
            q_network_target.load_weights(model_dir + ".h5")

            dqn_agent = DQNAgent((q_network_online, q_network_target), preprocessor, memory, policy, num_actions,
                                 args.gamma, args.target_update_freq, args.num_burn_in, args.train_freq,
                                 args.batch_size, \
                                 args.experience_replay, args.repetition_times, args.network_name, args.max_grad,
                                 args.env, sess)

            dqn_agent.evaluate(env, log_file, args.eval_num)
        exit(0)

    '''Train the model'''
    q_network_online = create_model(args.window, args.new_size, num_actions, args.network_name, True)
    q_network_target = create_model(args.window, args.new_size, num_actions, args.network_name, False)

    # create output dir, meant to pop up error when dir exist to avoid over written
    os.mkdir(os.path.join(args.output, args.network_name))

    with tf.Session() as sess:
        dqn_agent = DQNAgent((q_network_online, q_network_target), preprocessor, memory, policy, num_actions,
                             args.gamma, args.target_update_freq, args.num_burn_in, args.train_freq, args.batch_size, \
                             args.experience_replay, args.repetition_times, args.network_name, args.max_grad, args.env,
                             sess)

        optimizer = tf.train.AdamOptimizer(learning_rate=args.alpha)
        dqn_agent.compile(optimizer, mean_huber_loss)
        dqn_agent.fit(env, args.num_iterations, os.path.join(args.output, args.network_name), args.save_freq,
                      args.max_episode_length)


if __name__ == '__main__':
    main()
