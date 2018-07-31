#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Evaluate the hierarchical ASR model."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from os.path import join, abspath
import sys
import argparse
from distutils.util import strtobool

sys.path.append(abspath('../../../'))
from src.models.load_model import load
from src.dataset.loader_hierarchical import Dataset as Dataset_asr
from src.dataset.loader_hierarchical_p2w import Dataset as Dataset_p2w
from src.metrics.character import eval_char
from src.metrics.word import eval_word
from src.utils.config import load_config
from src.utils.evaluation.logging import set_logger

parser = argparse.ArgumentParser()
parser.add_argument('--corpus', type=str,
                    help='the name of corpus')
parser.add_argument('--eval_sets', type=str, nargs='+',
                    help='evaluation sets')
parser.add_argument('--data_save_path', type=str,
                    help='path to saved data')
parser.add_argument('--model_path', type=str,
                    help='path to the model to evaluate')
parser.add_argument('--epoch', type=int, default=-1,
                    help='the epoch to restore')
parser.add_argument('--eval_batch_size', type=int, default=1,
                    help='the size of mini-batch in evaluation')

# main task
parser.add_argument('--beam_width', type=int, default=1,
                    help='the size of beam of the main task')
parser.add_argument('--length_penalty', type=float, default=0,
                    help='length penalty of the main task')
parser.add_argument('--coverage_penalty', type=float, default=0,
                    help='coverage penalty of the main task')
parser.add_argument('--rnnlm_weight', type=float, default=0,
                    help='the weight of RNNLM score of the main task')
parser.add_argument('--rnnlm_path', default=None, type=str,  nargs='?',
                    help='path to the RMMLM of the main task')

# sub task
parser.add_argument('--beam_width_sub', type=int, default=1,
                    help='the size of beam of the sub task')
parser.add_argument('--length_penalty_sub', type=float, default=0,
                    help='length penalty of the sub task')
parser.add_argument('--coverage_penalty_sub', type=float, default=0,
                    help='coverage penalty_sub of the sub task')
parser.add_argument('--rnnlm_weight_sub', type=float, default=0,
                    help='the weight of RNNLM score of the sub task')
parser.add_argument('--rnnlm_path_sub', default=None, type=str, nargs='?',
                    help='path to the RMMLM of the sub task')

parser.add_argument('--resolving_unk', type=strtobool, default=False)
parser.add_argument('--a2c_oracle', type=strtobool, default=False)
parser.add_argument('--joint_decoding', type=strtobool, default=False)
parser.add_argument('--score_sub_weight', type=float, default=0)
parser.add_argument('--score_sub_task', type=strtobool, default=False)
args = parser.parse_args()

# corpus depending
if args.corpus == 'csj':
    MAX_DECODE_LEN_WORD = 100
    MIN_DECODE_LEN_WORD = 1
    MAX_DECODE_LEN_RATIO_WORD = 1
    MIN_DECODE_LEN_RATIO_WORD = 0

    MAX_DECODE_LEN_CHAR = 200
    MIN_DECODE_LEN_CHAR = 1
    MAX_DECODE_LEN_RATIO_CHAR = 1
    MIN_DECODE_LEN_RATIO_CHAR = 0.2

    MAX_DECODE_LEN_PHONE = 200
    MIN_DECODE_LEN_PHONE = 1
    MAX_DECODE_LEN_RATIO_PHONE = 1
    MIN_DECODE_LEN_RATIO_PHONE = 0
elif args.corpus == 'swbd':
    MAX_DECODE_LEN_WORD = 100
    MIN_DECODE_LEN_WORD = 1
    MAX_DECODE_LEN_RATIO_WORD = 1
    MIN_DECODE_LEN_RATIO_WORD = 0

    MAX_DECODE_LEN_CHAR = 300
    MIN_DECODE_LEN_CHAR = 1
    MAX_DECODE_LEN_RATIO_CHAR = 1
    MIN_DECODE_LEN_RATIO_CHAR = 0.1

    MAX_DECODE_LEN_PHONE = 300
    MIN_DECODE_LEN_PHONE = 1
    MAX_DECODE_LEN_RATIO_PHONE = 1
    MIN_DECODE_LEN_RATIO_PHONE = 0.05
elif args.corpus == 'librispeech':
    MAX_DECODE_LEN_WORD = 200
    MIN_DECODE_LEN_WORD = 1
    MAX_DECODE_LEN_RATIO_WORD = 1
    MIN_DECODE_LEN_RATIO_WORD = 0

    MAX_DECODE_LEN_CHAR = 600
    MIN_DECODE_LEN_CHAR = 1
    MAX_DECODE_LEN_RATIO_CHAR = 1
    MIN_DECODE_LEN_RATIO_CHAR = 0.2
elif args.corpus == 'wsj':
    MAX_DECODE_LEN_WORD = 32
    MIN_DECODE_LEN_WORD = 2
    MAX_DECODE_LEN_RATIO_WORD = 1
    MIN_DECODE_LEN_RATIO_WORD = 0

    MAX_DECODE_LEN_CHAR = 199
    MIN_DECODE_LEN_CHAR = 10
    MAX_DECODE_LEN_RATIO_CHAR = 1
    MIN_DECODE_LEN_RATIO_CHAR = 0.2

    MAX_DECODE_LEN_PHONE = 200
    MIN_DECODE_LEN_PHONE = 1
    MAX_DECODE_LEN_RATIO_PHONE = 1
    MIN_DECODE_LEN_RATIO_PHONE = 0
    # NOTE:
    # dev93 (char): 10-199
    # test_eval92 (char): 16-195
    # dev93 (word): 2-32
    # test_eval92 (word): 3-30
elif args.corpus == 'timit':
    MAX_DECODE_LEN_PHONE = 71
    MIN_DECODE_LEN_PHONE = 13
    MAX_DECODE_LEN_RATIO_PHONE = 1
    MIN_DECODE_LEN_RATIO_PHONE = 0
    # NOTE*
    # dev: 13-71
    # test: 13-69
else:
    raise ValueError(args.corpus)


def main():

    # Load a ASR config file
    config = load_config(join(args.model_path, 'config.yml'), is_eval=True)

    # Setting for logging
    logger = set_logger(args.model_path)

    wer_mean, wer_sub_mean, cer_sub_mean = 0, 0, 0
    for i, data_type in enumerate(args.eval_sets):
        # Load dataset
        if config['input_type'] == 'speech':
            eval_set = Dataset_asr(
                corpus=args.corpus,
                data_save_path=args.data_save_path,
                model_type=config['model_type'],
                input_freq=config['input_freq'],
                use_delta=config['use_delta'],
                use_double_delta=config['use_double_delta'],
                data_size=config['data_size'] if 'data_size' in config.keys(
                ) else '',
                vocab=config['vocab'],
                data_type=data_type,
                label_type=config['label_type'],
                label_type_sub=config['label_type_sub'],
                batch_size=args.eval_batch_size,
                tool=config['tool'])
        elif config['input_type'] == 'text':
            eval_set = Dataset_p2w(
                corpus=args.corpus,
                data_save_path=args.data_save_path,
                model_type=config['model_type'],
                data_type=data_type,
                data_size=config['data_size'] if 'data_size' in config.keys(
                ) else '',
                vocab=config['vocab'],
                label_type_in=config['label_type_in'],
                label_type=config['label_type'],
                label_type_sub=config['label_type_sub'],
                batch_size=args.eval_batch_size,
                sort_utt=False, reverse=False, tool=config['tool'],
                use_ctc=config['model_type'] == 'hierarchical_ctc',
                subsampling_factor=2 ** sum(config['subsample_list']),
                use_ctc_sub=config['model_type'] == 'hierarchical_ctc' or (
                    config['model_type'] == 'hierarchical_attention' and config['ctc_loss_weight_sub'] > 0),
                subsampling_factor_sub=2 ** sum(config['subsample_list'][:config['encoder_num_layers_sub'] - 1]))
            if i == 0:
                config['num_classes_input'] = eval_set.num_classes_in

        if i == 0:
            config['num_classes'] = eval_set.num_classes
            config['num_classes_sub'] = eval_set.num_classes_sub

            # For cold fusion
            if config['rnnlm_fusion_type'] and config['rnnlm_path']:
                # Load a RNNLM config file
                config['rnnlm_config'] = load_config(
                    join(args.model_path, 'config_rnnlm.yml'))
                assert config['label_type'] == config['rnnlm_config']['label_type']
                config['rnnlm_config']['num_classes'] = eval_set.num_classes
                logger.info('RNNLM path (main): %s' % config['rnnlm_path'])
                logger.info('RNNLM weight (main): %.3f' % args.rnnlm_weight)
            else:
                config['rnnlm_config'] = None

            if config['rnnlm_fusion_type'] and config['rnnlm_path_sub']:
                # Load a RNNLM config file
                config['rnnlm_config_sub'] = load_config(
                    join(args.model_path, 'config_rnnlm_sub.yml'))
                assert config['label_type_sub'] == config['rnnlm_config_sub']['label_type']
                config['rnnlm_config_sub']['num_classes'] = eval_set.num_classes_sub
                logger.info('RNNLM path (sub): %s' % config['rnnlm_path_sub'])
                logger.info('RNNLM weight (sub): %.3f' % args.rnnlm_weight_sub)
            else:
                config['rnnlm_config_sub'] = None

            # Load the ASR model
            model = load(model_type=config['model_type'],
                         config=config,
                         backend=config['backend'])

            # Restore the saved parameters
            epoch, _, _, _ = model.load_checkpoint(
                save_path=args.model_path, epoch=args.epoch)

            # For shallow fusion
            if not (config['rnnlm_fusion_type'] and config['rnnlm_path']) and args.rnnlm_path is not None and args.rnnlm_weight > 0:
                # Load a RNNLM config file
                config_rnnlm = load_config(
                    join(args.rnnlm_path, 'config.yml'), is_eval=True)
                assert config['label_type'] == config_rnnlm['label_type']
                config_rnnlm['num_classes'] = eval_set.num_classes

                # Load the pre-trianed RNNLM
                rnnlm = load(model_type=config_rnnlm['model_type'],
                             config=config_rnnlm,
                             backend=config_rnnlm['backend'])
                rnnlm.load_checkpoint(save_path=args.rnnlm_path, epoch=-1)
                rnnlm.flatten_parameters()
                model.rnnlm_0_fwd = rnnlm
                logger.info('RNNLM path (main): %s' % args.rnnlm_path)
                logger.info('RNNLM weight (main): %.3f' % args.rnnlm_weight)

            if not (config['rnnlm_fusion_type'] and config['rnnlm_path_sub']) and args.rnnlm_path_sub is not None and args.rnnlm_weight_sub > 0:
                # Load a RNNLM config file
                config_rnnlm_sub = load_config(
                    join(args.rnnlm_path_sub, 'config.yml'), is_eval=True)
                assert config['label_type_sub'] == config_rnnlm_sub['label_type']
                config_rnnlm_sub['num_classes'] = eval_set.num_classes_sub

                # Load the pre-trianed RNNLM
                rnnlm_sub = load(model_type=config_rnnlm_sub['model_type'],
                                 config=config_rnnlm_sub,
                                 backend=config_rnnlm_sub['backend'])
                rnnlm_sub.load_checkpoint(
                    save_path=args.rnnlm_path_sub, epoch=-1)
                rnnlm_sub.flatten_parameters()
                model.rnnlm_1_fwd = rnnlm_sub
                logger.info('RNNLM path (sub): %s' % args.rnnlm_path_sub)
                logger.info('RNNLM weight (sub): %.3f' % args.rnnlm_weight_sub)

            # GPU setting
            model.set_cuda(deterministic=False, benchmark=True)

            logger.info('beam width (main): %d' % args.beam_width)
            logger.info('length penaly (main): %.3f' % args.length_penalty)
            logger.info('coverage penaly (main): %.3f' % args.coverage_penalty)
            logger.info('beam width (sub) : %d' % args.beam_width_sub)
            logger.info('length penaly (sub): %.3f' % args.length_penalty_sub)
            logger.info('coverage penaly (sub): %.3f' %
                        args.coverage_penalty_sub)
            logger.info('epoch: %d' % (epoch - 1))
            logger.info('a2c oracle: %s' % str(args.a2c_oracle))
            logger.info('resolving_unk: %s' % str(args.resolving_unk))
            logger.info('joint_decoding: %s' % str(args.joint_decoding))
            logger.info('score_sub_weight : %.3f' % args.score_sub_weight)

        if not args.score_sub_task:
            wer, df = eval_word(
                models=[model],
                dataset=eval_set,
                eval_batch_size=args.eval_batch_size,
                beam_width=args.beam_width,
                max_decode_len=MAX_DECODE_LEN_WORD,
                min_decode_len=MIN_DECODE_LEN_WORD,
                min_decode_len_ratio=MIN_DECODE_LEN_RATIO_WORD,
                length_penalty=args.length_penalty,
                coverage_penalty=args.coverage_penalty,
                rnnlm_weight=args.rnnlm_weight,
                beam_width_sub=args.beam_width_sub,
                max_decode_len_sub=MAX_DECODE_LEN_CHAR,
                min_decode_len_sub=MIN_DECODE_LEN_CHAR,
                min_decode_len_ratio_sub=MIN_DECODE_LEN_RATIO_CHAR,
                length_penalty_sub=args.length_penalty_sub,
                coverage_penalty_sub=args.coverage_penalty_sub,
                rnnlm_weight_sub=args.rnnlm_weight_sub,
                resolving_unk=args.resolving_unk,
                a2c_oracle=args.a2c_oracle,
                joint_decoding=args.joint_decoding,
                score_sub_weight=args.score_sub_weight,
                progressbar=True)
            wer_mean += wer
            logger.info('  WER (%s, main): %.3f %%' % (data_type, wer))
            logger.info(df)

        else:
            wer, cer, df = eval_char(
                models=[model],
                dataset=eval_set,
                eval_batch_size=args.eval_batch_size,
                beam_width=args.beam_width_sub,
                max_decode_len=MAX_DECODE_LEN_CHAR,
                min_decode_len=MIN_DECODE_LEN_CHAR,
                min_decode_len_ratio=MIN_DECODE_LEN_RATIO_CHAR,
                length_penalty=args.length_penalty_sub,
                coverage_penalty=args.coverage_penalty_sub,
                rnnlm_weight=args.rnnlm_weight_sub,
                progressbar=True)
            wer_sub_mean += wer
            cer_sub_mean += cer
            logger.info(' WER / CER (%s, sub): %.3f / %.3f %%' %
                        (data_type, wer, cer))
            logger.info(df)

    if not args.score_sub_task:
        logger.info('  WER (mean, main): %.3f %%' %
                    (wer_mean / len(args.eval_sets)))
    else:
        logger.info('  WER / CER (mean, sub): %.3f / %.3f %%\n' %
                    (wer_sub_mean / len(args.eval_sets),
                     cer_sub_mean / len(args.eval_sets)))


if __name__ == '__main__':
    main()