import tensorflow as tf
import numpy as np
import sys
from random import randint
import datetime
from sklearn.utils import shuffle
import pickle
import os
os.environ['TF_CPP_MIN_LOG_LEVEL']='2'

def createTrainingMatrices(conversationFileName, wList, maxLen):
	conversationDictionary = np.load(conversationFileName).item()
	numExamples = len(conversationDictionary)
	xTrain = np.zeros((numExamples, maxLen), dtype='int32')
	yTrain = np.zeros((numExamples, maxLen), dtype='int32')
	for index,(key,value) in enumerate(conversationDictionary.items()):
		encoderMessage = np.full((maxLen), wList.index('<pad>'), dtype='int32')
		decoderMessage = np.full((maxLen), wList.index('<pad>'), dtype='int32')
		keySplit = key.split()
		valueSplit = value.split()
		keyCount = len(keySplit)
		valueCount = len(valueSplit)
		if (keyCount > (maxLen - 1) or valueCount > (maxLen - 1)):
			continue
		for keyIndex, word in enumerate(keySplit):
			try:
				encoderMessage[keyIndex] = wList.index(word)
			except ValueError:
				encoderMessage[keyIndex] = 0
		encoderMessage[keyIndex + 1] = wList.index('<EOS>')
		for valueIndex, word in enumerate(valueSplit):
			try:
				decoderMessage[valueIndex] = wList.index(word)
			except ValueError:
				decoderMessage[valueIndex] = 0
		decoderMessage[valueIndex + 1] = wList.index('<EOS>')
		xTrain[index] = encoderMessage
		yTrain[index] = decoderMessage
	yTrain = yTrain[~np.all(yTrain == 0, axis=1)]
	xTrain = xTrain[~np.all(xTrain == 0, axis=1)]
	numExamples = xTrain.shape[0]
	return numExamples, xTrain, yTrain

def getTrainingBatch(localXTrain, localYTrain, localBatchSize, maxLen):
	num = randint(0,numTrainingExamples - localBatchSize - 1)
	arr = localXTrain[num:num + localBatchSize]
	labels = localYTrain[num:num + localBatchSize]
	#reverse encoder
	reversedList = list(arr)
	for index,example in enumerate(reversedList):
		reversedList[index] = list(reversed(example))

	laggedLabels = []
	EOStokenIndex = wordList.index('<EOS>')
	padTokenIndex = wordList.index('<pad>')
	for example in labels:
		eosFound = np.argwhere(example==EOStokenIndex)[0]
		shiftedExample = np.roll(example,1)
		shiftedExample[0] = EOStokenIndex
		if (eosFound != (maxLen - 1)):
			shiftedExample[eosFound+1] = padTokenIndex
		laggedLabels.append(shiftedExample)

	reversedList = np.asarray(reversedList).T.tolist()
	labels = labels.T.tolist()
	laggedLabels = np.asarray(laggedLabels).T.tolist()
	return reversedList, labels, laggedLabels

def translateToSentences(inputs, wList, encoder=False):
	EOStokenIndex = wList.index('<EOS>')
	padTokenIndex = wList.index('<pad>')
	numStrings = len(inputs[0])
	numLengthOfStrings = len(inputs)
	listOfStrings = [''] * numStrings
	for mySet in inputs:
		for index,num in enumerate(mySet):
			if (num != EOStokenIndex and num != padTokenIndex):
				if (encoder):
					listOfStrings[index] = wList[num] + " " + listOfStrings[index]
				else:
					listOfStrings[index] = listOfStrings[index] + " " + wList[num]
	listOfStrings = [string.strip() for string in listOfStrings]
	return listOfStrings

def getTestInput(inputMessage, wList, maxLen):
	encoderMessage = np.full((maxLen), wList.index('<pad>'), dtype='int32')
	inputSplit = inputMessage.lower().split()
	for index,word in enumerate(inputSplit):
		try:
			encoderMessage[index] = wList.index(word)
		except ValueError:
			continue
	encoderMessage[index + 1] = wList.index('<EOS>')
	encoderMessage = encoderMessage[::-1]
	encoderMessageList=[]
	for num in encoderMessage:
		encoderMessageList.append([num])
	return encoderMessageList

def idsToSentence(ids, wList):
    EOStokenIndex = wList.index('<EOS>')
    padTokenIndex = wList.index('<pad>')
    myStr = ""
    listOfResponses=[]
    for num in ids:
        if (num[0] == EOStokenIndex or num[0] == padTokenIndex):
            listOfResponses.append(myStr)
            myStr = ""
        else:
            myStr = myStr + wList[num[0]] + " "
    if myStr:
        listOfResponses.append(myStr)
    listOfResponses = [i for i in listOfResponses if i]
    return listOfResponses

batchSize = 24
maxEncoderLength = 15
maxDecoderLength = maxEncoderLength
lstmUnits = 112
embeddingDim = lstmUnits
numLayersLSTM = 3
numIterations = 100000

wordList = []

with open("../wordembeddings/wordList.txt") as f:
	wordList = f.readlines()
wordList = [x.strip() for x in wordList]

wordVectors = np.load('../wordembeddings/embeddingMatrix.npy')
vocabSize = len(wordList)
wordVecDimensions = wordVectors.shape[1]

padVector = np.zeros((1, wordVecDimensions), dtype='int32')
EOSVector = np.ones((1, wordVecDimensions), dtype='int32')
wordVectors = np.concatenate((wordVectors,padVector), axis=0)
wordVectors = np.concatenate((wordVectors,EOSVector), axis=0)

wordList.append('<pad>')
wordList.append('<EOS>')
vocabSize = vocabSize + 2

numTrainingExamples, xTrain, yTrain = createTrainingMatrices('../preprocessing/conversationDictionary.npy', wordList, maxEncoderLength)
np.save('Seq2SeqXTrain.npy', xTrain)
np.save('Seq2SeqYTrain.npy', yTrain)
print('Finished creating training matrices')

tf.reset_default_graph()

encoderInputs = [tf.placeholder(tf.int32, shape=(None,)) for i in range(maxEncoderLength)]
decoderLabels = [tf.placeholder(tf.int32, shape=(None,)) for i in range(maxDecoderLength)]
decoderInputs = [tf.placeholder(tf.int32, shape=(None,)) for i in range(maxDecoderLength)]
feedPrevious = tf.placeholder(tf.bool)

encoderLSTM = tf.nn.rnn_cell.BasicLSTMCell(lstmUnits, state_is_tuple=True)

decoderOutputs, decoderFinalState = tf.contrib.legacy_seq2seq.embedding_rnn_seq2seq(encoderInputs, decoderInputs, encoderLSTM,
															vocabSize, vocabSize, embeddingDim, feed_previous=feedPrevious)

decoderPrediction = tf.argmax(decoderOutputs, 2)

lossWeights = [tf.ones_like(l, dtype=tf.float32) for l in decoderLabels]
loss = tf.contrib.legacy_seq2seq.sequence_loss(decoderOutputs, decoderLabels, lossWeights, vocabSize)
optimizer = tf.train.AdamOptimizer(1e-4).minimize(loss)

sess = tf.Session()
saver = tf.train.Saver()
sess.run(tf.global_variables_initializer())

tf.summary.scalar('Loss', loss)
merged = tf.summary.merge_all()
logdir = "tensorboard/" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "/"
writer = tf.summary.FileWriter(logdir, sess.graph)

# Some test strings that we'll use as input at intervals during training
encoderTestStrings = ["whats up",
					"hi",
					"hey how are you",
					"what are you doing",
					"that star wars movie was awesome"
					]

zeroVector = np.zeros((1), dtype='int32')

for i in range(numIterations):

	encoderTrain, decoderTargetTrain, decoderInputTrain = getTrainingBatch(xTrain, yTrain, batchSize, maxEncoderLength)
	feedDict = {encoderInputs[t]: encoderTrain[t] for t in range(maxEncoderLength)}
	feedDict.update({decoderLabels[t]: decoderTargetTrain[t] for t in range(maxDecoderLength)})
	feedDict.update({decoderInputs[t]: decoderInputTrain[t] for t in range(maxDecoderLength)})
	feedDict.update({feedPrevious: False})

	curLoss, _, pred = sess.run([loss, optimizer, decoderPrediction], feed_dict=feedDict)

	if (i % 50 == 0):
		print('Current loss:', curLoss, 'at iteration', i)
		summary = sess.run(merged, feed_dict=feedDict)
		writer.add_summary(summary, i)
	if (i % 25 == 0 and i != 0):
		num = randint(0,len(encoderTestStrings) - 1)
		print(encoderTestStrings[num])
		inputVector = getTestInput(encoderTestStrings[num], wordList, maxEncoderLength);
		feedDict = {encoderInputs[t]: inputVector[t] for t in range(maxEncoderLength)}
		feedDict.update({decoderLabels[t]: zeroVector for t in range(maxDecoderLength)})
		feedDict.update({decoderInputs[t]: zeroVector for t in range(maxDecoderLength)})
		feedDict.update({feedPrevious: True})
		ids = (sess.run(decoderPrediction, feed_dict=feedDict))
		print(idsToSentence(ids, wordList))

	if (i % 10000 == 0 and i != 0):
		savePath = saver.save(sess, "models/pretrained_seq2seq.ckpt", global_step=i)
