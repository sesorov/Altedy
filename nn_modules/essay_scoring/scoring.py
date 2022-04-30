import numpy as np
import pandas as pd
import nltk
import re
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize
from gensim.models import Word2Vec
from keras.layers import Embedding, LSTM, Dense, Dropout, Lambda, Flatten
from keras.models import Sequential, load_model, model_from_config
from gensim.models.keyedvectors import KeyedVectors
import keras.backend as K
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from sklearn.metrics import cohen_kappa_score

nltk.download('stopwords')
nltk.download('punkt')


LSTM_MODEL_PATH = "nn_modules/essay_scoring/model_lstm.pth"
WORD2VEC_MODEL_PATH = "nn_modules/essay_scoring/model_w2v.pth"


def split_sentence(sentence):
    """
    Split sentence into words excluding punctuation and numbers

    :param sentence:
    :return:
    """

    sentence_clean = re.sub("[^A-Za-z]", " ", sentence)
    sentence_clean.lower()
    words = sentence_clean.split()

    filtered_sentence = []
    stop_words = set(stopwords.words('english'))
    for w in words:
        if w not in stop_words:
            filtered_sentence.append(w)
    return filtered_sentence


def split_text(text):
    """
    Split text into words excluding punctuation and numbers

    :param text:
    :return:
    """

    text_stripped = text.strip()
    tokenizer = nltk.data.load('tokenizers/punkt/english.pickle')
    raw = tokenizer.tokenize(text_stripped)

    final_words = []
    for i in raw:
        if len(i) > 0:
            final_words.append(split_sentence(i))
    return final_words


def get_vector(words, model, num_features):
    """
    Get words vector

    :param words:
    :param model:
    :param num_features:
    :return:
    """

    vec = np.zeros((num_features,), dtype="float32")
    word_count = 0.
    index_to_key_set = set(model.index_to_key)

    for i in words:
        if i in index_to_key_set:
            word_count += 1
            vec = np.add(vec, model[i])
    vec = np.divide(vec, word_count)
    return vec


def sentences_vectors(sentences, model, num_features):
    """
    Get text vectors

    :param sentences:
    :param model:
    :param num_features:
    :return:
    """

    essay_vecs = np.zeros((len(sentences), num_features), dtype="float32")
    for i, sentence in enumerate(sentences):
        essay_vecs[i] = get_vector(sentence, model, num_features)
    return essay_vecs


def get_model():
    """
    Get LSTM model instance

    :return:
    """
    model = Sequential()
    model.add(LSTM(300, dropout=0.4, recurrent_dropout=0.4, input_shape=[1, 300], return_sequences=True))
    model.add(LSTM(64, recurrent_dropout=0.4))
    model.add(Dropout(0.5))
    model.add(Dense(1, activation='relu'))
    model.compile(loss='mean_squared_error', optimizer='rmsprop', metrics=['mae'])
    model.summary()
    return model


def score_text(text):
    """
    Grade provided text 1-10

    :param text: str
    :return: int
    """

    if len(text) > 20:
        num_features = 300
        model = KeyedVectors.load_word2vec_format(WORD2VEC_MODEL_PATH, binary=True)
        clean_sentences = [split_sentence(text)]
        text_vectors = sentences_vectors(clean_sentences, model, num_features)
        text_vectors = np.array(text_vectors)
        text_vectors = np.reshape(text_vectors, (text_vectors.shape[0], 1, text_vectors.shape[1]))

        lstm_model = load_model(LSTM_MODEL_PATH)
        pred = lstm_model.predict(text_vectors)
        return str(round(pred[0][0]))
