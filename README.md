# prompttest

[![Build Status](https://github.com/decodingchris/prompttest/actions/workflows/ci.yml/badge.svg)](https://github.com/decodingchris/prompttest/actions)
[![PyPI version](https://img.shields.io/pypi/v/prompttest.svg)](https://pypi.org/project/prompttest/)
[![PyPI - Python Versions](https://img.shields.io/pypi/pyversions/prompttest.svg)](https://pypi.org/project/prompttest/)
[![PyPI downloads](https://img.shields.io/pypi/dm/prompttest.svg)](https://pypi.org/project/prompttest/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/decodingchris/prompttest/blob/main/LICENSE)

pytest for LLMs.

You wouldn't ship code without tests. ✋😮🤚

Hold your prompts to the same standard. 😎👌🔥

![A demo of prompttest](https://raw.githubusercontent.com/decodingchris/prompttest/main/demo.gif)

## Features

- **🔤 Test in Plain English:** Write your tests in English, and let an AI grade the response.

- **🚀 Write Tests Faster:** Just list your inputs and criteria in a simple file—no code needed.

- **🔓 Avoid Vendor Lock-in:** Test against any LLM with a single, free OpenRouter API key.

## Quick Start

### 1. Install prompttest

```bash
pip install prompttest
```

### 2. Set up prompttest

```bash
prompttest init
```

### 3. Run your tests

```bash
prompttest
```

## How It Works

prompttest is built around 2 types of files:

### Prompt

A `.txt` file for your prompt template with `---[SECTIONS]---` and `{variables}`.

Example: `prompts/customer_service.txt`

```txt
---[SYSTEM]---
You are an expert on the "{product_name}".
Your responses must be helpful and polite.

---[USER]---
Customer tier: {user_tier}
Customer query: {user_query}
```

### Test

A  `.yml` file for test cases with `config`, `inputs` and `criteria`.

Example: `prompttests/test_customer_service.yml`

```yaml
config:
  prompt: customer_service

tests:
  - id: check-simple-greeting
    inputs:
      product_name: "Chrono-Watch"
      user_tier: "Standard"
      user_query: "Hello"
    criteria: "The response must be a simple, polite greeting."
```

## Advanced Usage

### Run all tests in a folder

```bash
prompttest run folder_name/
```

### Run all tests in a file

```bash
prompttest run file_name.yml
```

### Run specific test

```bash
prompttest run test_id
```

## Contributing

We're building the pytest for LLMs—and we need your help.

Report a bug, propose a feature, or contribute a single line.

Help shape a foundational tool for AI development.

## License

This project is licensed under the MIT License.
