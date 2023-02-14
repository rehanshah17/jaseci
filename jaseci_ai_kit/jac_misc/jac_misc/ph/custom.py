import torch
from torch import nn
from torch.utils.data import Dataset
from typing import Iterable, Dict, Optional, List
from torch import LongTensor
from jac_nlp.bi_ner.model.ph_func import BI_P_Head, prepare_inputs
from jac_nlp.bi_ner.model.loss import ContrastiveThresholdLoss
from jac_nlp.bi_ner.model.tokenize_data import get_datasets
from jac_nlp.bi_ner.datamodel.utils import get_category_id_mapping, invert
from jac_nlp.bi_ner.datamodel.example import (
    Example,
    batch_examples,
    BatchedExamples,
    TypedSpan,
)
from jac_nlp.bi_ner.datamodel import example
from functools import partial
from torch.nn.functional import pad
from jac_misc.ph.utils.base import BaseInference
from typing import Any
from collections import defaultdict
import json

def collate_fn(
    examples: Iterable[Example],
    _max_sequence_length=128,
    return_batch_examples: bool = False,
) -> Dict[str, Optional[LongTensor]]:
    print("custom collate fucntions")
    # print(examples)
    return example.collate_examples(
        examples,
        padding_token_id=100,
        pad_length=_max_sequence_length,
        return_batch_examples=return_batch_examples,
    )


class CustomLoss(torch.nn.Module):
    def __init__(self, n_classes=2, beta=0.6):
        super(CustomLoss, self).__init__()
        self._loss_fn = ContrastiveThresholdLoss(
            n_classes=n_classes, ignore_id=-100, reduction="mean", beta=beta
        )

    def forward(self, output, labels):
        _span_coef = 0.6
        _start_coef = 0.2
        _end_coef = 0.2
        _max_entity_length = 30

        span_loss = self._loss_fn(output[0], labels)
        start_loss = self._loss_fn(
            output[1].unsqueeze(-2).repeat(1, 1, _max_entity_length, 1), labels
        )
        end_loss = self._loss_fn(
            output[2].unsqueeze(-2).repeat(1, 1, _max_entity_length, 1), labels
        )

        return _span_coef * span_loss + _start_coef * start_loss + _end_coef * end_loss


class CustomModel(nn.Module):
    def __init__(self, model_args) -> None:
        super(CustomModel, self).__init__()
        self.model = BI_P_Head(model_args)
        print(f"in custom model{model_args}")
        con_encoder_layer = nn.TransformerEncoderLayer(
            d_model=768,
            nhead=12,
            dim_feedforward=128,
            batch_first=True,
        )
        cand_encoder_layer = nn.TransformerEncoderLayer(
            d_model=768,
            nhead=12,
            dim_feedforward=30,
            batch_first=True,
        )
        self.con_encoder = nn.TransformerEncoder(
            encoder_layer=con_encoder_layer, num_layers=1
        )
        self.cand_encoder = nn.TransformerEncoder(
            encoder_layer=cand_encoder_layer, num_layers=1
        )

    def forward(self, x):
        label = "train"
        print(x.ndimension())
        if x.ndimension() == 1:
            x = x.unsqueeze(0)
            label = None
        ent_emb, token_emb = self.model(x)
        token_emb = self.con_encoder(token_emb)
        ent_emb = self.cand_encoder(ent_emb)
        scores = self.model.get_scores(token_emb, ent_emb, label)
        return scores


class CustomDataset(Dataset):
    def __init__(self, train_args) -> None:
        super(CustomDataset, self).__init__()
        with open("/home/ubuntu/jaseci/jaseci_ai_kit/jac_misc/jac_misc/ph/ph_train_data.json","r") as fp:
          self.data = json.load(fp)
        category_id_mapping = get_category_id_mapping(
            train_args, train_args["descriptions"]
        )
        self.example_encoder = partial(
            prepare_inputs,
            category_mapping=invert(category_id_mapping),
            no_entity_category=train_args["unk_category"],
        )
        self.dataset = get_datasets(self.data, self.example_encoder)

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, idx):
        return self.dataset[idx]


class CustomInference(BaseInference):
    @torch.no_grad()
    def predict(self, data: Any) -> Any:
        self._max_entity_length = 30
        inf_args = {
            "unk_entity_type_id": -1,
            "unk_category": "<UNK>",
            "max_sequence_length": 128,
            "descriptions": ["Fin_Corp"],
        }
        category_id_mapping = get_category_id_mapping(
            inf_args, inf_args["descriptions"]
        )
        category_mapping = invert(category_id_mapping)
        self._no_entity_category = inf_args["unk_category"]
        self._no_entity_category_id = inf_args["unk_entity_type_id"]
        self.stride = 0.9
        self._stride_length = int(inf_args["max_sequence_length"] * self.stride)
        # tokenization and data transformation
        self._text_length: List[Optional[int]] = [None] * len(data)
        examples = list(
            prepare_inputs(
                [data],
                [None] * len([data]),
                category_mapping=category_mapping,
                no_entity_category=self._no_entity_category,
                stride=self.stride,
                text_lengths=self._text_length,
            )
        )
        example = batch_examples(
            examples,
            batch_size=1,
            collate_fn=partial(collate_fn, return_batch_examples=True),
        )
        # model_predictions = inference_model(x)
        # print(example)
        predictions_collector = [defaultdict(int) for _ in [data]]
        for batch in example:
            # print(batch)
            data = batch["input_ids"]
            data = data.to(self.device)
            print(data)
            predictions = self.model(data[0])
            batched_examples: BatchedExamples = batch["examples"]

            batch_size, length = batched_examples.start_offset.shape
            span_start = (
                pad(
                    batched_examples.start_offset,
                    [0, inf_args["max_sequence_length"] - length],
                    value=-100,
                )
                .view(batch_size, inf_args["max_sequence_length"], 1)
                .repeat(1, 1, self._max_entity_length)
                .to(self.device)
            )

            end_offset = pad(
                batched_examples.end_offset,
                [0, inf_args["max_sequence_length"] - length],
                value=-100,
            ).to(self.device)

            padding_masks = []
            span_end = []
            for shift in range(
                self._max_entity_length
            ):  # self._max_entity_length ~ 20-30, so it is fine to not vectorize this
                span_end.append(torch.roll(end_offset, -shift, 1).unsqueeze(-1))
                padding_mask = torch.roll(end_offset != -100, -shift, 1)
                padding_mask[:, -shift:] = False
                padding_masks.append(padding_mask.unsqueeze(-1))

            span_end = torch.concat(span_end, dim=-1)
            padding_mask = torch.concat(padding_masks, dim=-1)
            print(predictions.shape)
            entities_mask = (
                (predictions != self._no_entity_category_id)
                & padding_mask
                & (span_end != -100)
                & (span_start != -100)
            )
            entity_token_start = (
                torch.arange(inf_args["max_sequence_length"])
                .reshape(1, inf_args["max_sequence_length"], 1)
                .repeat(batch_size, 1, self._max_entity_length)
                .to(self.device)
            )

            entity_text_ids = (
                torch.tensor(batched_examples.text_ids)
                .view(batch_size, 1, 1)
                .repeat(1, inf_args["max_sequence_length"], self._max_entity_length)
                .to(self.device)
            )
            # print(predictions)
            chosen_text_ids = entity_text_ids[entities_mask]
            chosen_category_ids = predictions[entities_mask]
            chosen_span_starts = span_start[entities_mask]
            chosen_span_ends = span_end[entities_mask]
            chosen_token_starts = entity_token_start[entities_mask]
            for text_id, category_id, start, end, token_start in zip(
                chosen_text_ids,
                chosen_category_ids,
                chosen_span_starts,
                chosen_span_ends,
                chosen_token_starts,
            ):
                predictions_collector[text_id][
                    (
                        TypedSpan(
                            start.item(),
                            end.item(),
                            self._category_id_mapping[category_id.item()],
                        ),
                        token_start.item(),
                    )
                ] += 1

        all_entities = [set() for _ in [data]]
        for text_id, preds in enumerate(predictions_collector):
            text_length = self._text_length[text_id]
            strided_text_length = (
                (text_length // self._stride_length)
                + (text_length % self._stride_length > 0)
            ) * self._stride_length
            for (entity, entity_token_start), count_preds in preds.items():
                # [1, 2, 3, ..., MAX, MAX, ..., MAX, MAX - 1, ..., 3, 2, 1]
                #  bin sizes are stride_length except for the last bin
                total_predictions = min(
                    (entity_token_start // self._stride_length) + 1,
                    (
                        max(strided_text_length - inf_args["max_sequence_length"], 0)
                        // self._stride_length
                    )
                    + 1,
                    ((strided_text_length - entity_token_start) // self._stride_length)
                    + 1,
                )
                if count_preds >= total_predictions // 2:
                    all_entities[text_id].add(entity)
        print(all_entities)
        return all_entities
