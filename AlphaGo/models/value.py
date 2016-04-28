from AlphaGo.preprocessing.preprocessing import Preprocess
import json
import keras.backend as K
from keras.layers import convolutional, Dense
from keras.layers.core import Flatten
from keras.models import Sequential, model_from_json


### Parameters obtained from paper ###
# K = 152                        # depth of convolutional layers
# LEARNING_RATE = .003           # initial learning rate
# DECAY = 8.664339379294006e-08  # rate of exponential learning_rate decay


class CNNValue(object):
    """A convolutional neural network to guess the reward at the end of the
    game for a given board state, under the optimal policy.
    """
    def __init__(self, feature_list, **kwargs):
        """create a value object that preprocesses according to feature_list
        and uses a neural network specified by keyword arguments (see
        create_network())
        """
        self.preprocessor = Preprocess(feature_list)
        kwargs["input_dim"] = self.preprocessor.output_dim
        self.model = CNNValue.create_network(**kwargs)
        self.forward = self._model_forward()

    def _model_forward(self):
        """Construct a function using the current keras backend that, when given a batch
        of inputs, simply processes them forward and returns the output

        The output has size (batch x 1); one value per input board

        This is as opposed to model.compile(), which takes a loss function
        and training method.

        c.f. https://github.com/fchollet/keras/issues/1426
        """
        forward_function = K.function([self.model.input], [self.model.output])

        # the forward_function returns a list of tensors
        # the first [0] gets the front tensor.
        return lambda inpt: forward_function([inpt])[0]

    def eval_state(self, state):
        """Given a GameState object, returns a value
        """
        tensor = self.preprocessor.state_to_tensor(state)
        # run the tensor through the network
        network_output = self.forward(tensor)
        return network_output[0]

    @staticmethod
    def create_network(**kwargs):
        """construct a convolutional neural network.

        Keword Arguments:
        - input_dim:            depth of features to be processed by first layer (no default)
        - board:                width of the go board to be processed (default 19)
        - filters_per_layer:    number of filters used on every layer (default 128)
        - layers:               number of convolutional steps (default 12)
        - filter_width_K:       (where K is between 1 and <layers>) width of filter on
                                layer K (default 3 except 1st layer which defaults to 5).
                                Must be odd.
        """
        defaults = {
            "board": 19,
            "filters_per_layer": 128,
            "layers": 12,  # layers 2-11 are identical to policy net
            "filter_width_1": 5
        }
        # copy defaults, but override with anything in kwargs
        params = defaults
        params.update(kwargs)

        # create the network:
        # a series of zero-paddings followed by convolutions
        # such that the output dimensions are also board x board
        network = Sequential()

        # create first layer
        network.add(convolutional.Convolution2D(
            input_shape=(params["input_dim"], params["board"], params["board"]),
            nb_filter=params["filters_per_layer"],
            nb_row=params["filter_width_1"],
            nb_col=params["filter_width_1"],
            init='uniform',
            activation='relu',
            border_mode='same'))

        # create all other layers
        # TODO: penultimate layer different in some way?
        for i in range(2, params["layers"] + 1):
            # use filter_width_K if it is there, otherwise use 3
            filter_key = "filter_width_%d" % i
            filter_width = params.get(filter_key, 3)
            network.add(convolutional.Convolution2D(
                nb_filter=params["filters_per_layer"],
                nb_row=filter_width,
                nb_col=filter_width,
                init='uniform',
                activation='relu',
                border_mode='same'))

        # the last layer maps each <filters_per_layer> feature to a number
        network.add(convolutional.Convolution2D(
            nb_filter=1,
            nb_row=1,
            nb_col=1,
            init='uniform',
            activation='linear',
            border_mode='same'))
        network.add(Flatten())
        network.add(Dense(256, init='uniform'))
        network.add(Dense(1, init='uniform', activation="tanh"))
        return network

    @staticmethod
    def load_model(json_file):
        """create a new CNNPolicy object from the architecture specified in json_file
        """
        with open(json_file, 'r') as f:
            object_specs = json.load(f)
        new_policy = CNNValue(object_specs['feature_list'])
        new_policy.model = model_from_json(object_specs['keras_model'])
        new_policy.forward = new_policy._model_forward()
        return new_policy

    def save_model(self, json_file):
        """write the network model and preprocessing features to the specified file
        """
        # this looks odd because we are serializing a model with json as a string
        # then making that the value of an object which is then serialized as
        # json again.
        # It's not as crazy as it looks. A CNNPolicy has 2 moving parts - the
        # feature preprocessing and the neural net, each of which gets a top-level
        # entry in the saved file. Keras just happens to serialize models with JSON
        # as well. Note how this format makes load_model fairly clean as well.
        object_specs = {
            'keras_model': self.model.to_json(),
            'feature_list': self.preprocessor.feature_list
        }
        # use the json module to write object_specs to file
        with open(json_file, 'w') as f:
            json.dump(object_specs, f)
