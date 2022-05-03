import string

import nltk

from gensim.models.doc2vec import Doc2Vec
from sklearn.metrics.pairwise import cosine_similarity

from configs.logger_conf import configure_logger

nltk.download('stopwords')
nltk.download('wordnet')
nltk.download('punkt')
nltk.download('omw-1.4')

from nltk.corpus import stopwords  # noqa
from nltk.tokenize import word_tokenize  # noqa
from nltk.stem import WordNetLemmatizer  # noqa

LEMMATIZER = WordNetLemmatizer()
LOGGER = configure_logger(__name__)


def preprocess(text):
    """
    Text preprocessing

    Steps:
     1. Convert to lowercase;
     2. Lammetize (It does not stem. Try to preserve structure not to overwrap with potential acronym);
     3. Drop stop words;
     4. Drop punctuation;
     5. Drop words with the length = 1;

    :param text:
    :return:
    """

    lowered = str.lower(text)

    stop_words = set(stopwords.words('english'))
    word_tokens = word_tokenize(lowered)

    words = []
    for w in word_tokens:
        if w not in stop_words:
            if w not in string.punctuation:
                if len(w) > 1:
                    lemmatized = LEMMATIZER.lemmatize(w)
                    words.append(lemmatized)
    return words


def process_similarity(base_document: str, documents: list, model=None):
    """
    Compare one document to list of others.
    Returns ID of the most similar document and the percentage of similarity.
    Model is taken from public repo: https://github.com/jhlau/doc2vec

    :param base_document: string
    :param documents: list
    :param model: str or Path
    :return: set (id, similarity_percentage)
    """

    if not model:
        model = f"nn_modules/plagiarism/doc2vec.bin"

    model = Doc2Vec.load(model)

    tokens = preprocess(base_document)

    # Only handle words that appear in the doc2vec pretrained vectors
    tokens = list(filter(lambda x: x in model.wv.vocab.keys(), tokens))

    base_vector = model.infer_vector(tokens)

    vectors = []
    for i, document in enumerate(documents):
        tokens = preprocess(document)
        tokens = list(filter(lambda x: x in model.wv.vocab.keys(), tokens))
        vector = model.infer_vector(tokens)
        vectors.append(vector)

        print("making vector at index:", i)

    scores = cosine_similarity([base_vector], vectors).flatten()

    highest_score = 0
    highest_score_index = 0
    for i, score in enumerate(scores):
        if highest_score < score:
            highest_score = score
            highest_score_index = i

    return highest_score_index, highest_score
