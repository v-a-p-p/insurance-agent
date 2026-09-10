from src.chat.prompt import extract_few_shot_examples


def test_extract_few_shot_examples_count():
    examples = extract_few_shot_examples(5)
    assert len(examples) == 5


def test_each_example_contains_messages():
    examples = extract_few_shot_examples(5)
    for example in examples:
        assert "[lead]:" in example or "[vendedor]:" in example
        assert len(example) > 50


def test_examples_are_formatted_as_transcript():
    examples = extract_few_shot_examples(3)
    for example in examples:
        lines = example.split("\n")
        for line in lines:
            if line.strip():
                assert line.startswith(("[lead]:", "[vendedor]:"))


def test_extract_variable_count():
    examples = extract_few_shot_examples(3)
    assert len(examples) == 3

    examples = extract_few_shot_examples(1)
    assert len(examples) == 1
