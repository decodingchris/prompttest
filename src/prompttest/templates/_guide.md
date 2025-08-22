# prompttest Guide

This guide covers the main features of `prompttest`.

## Main Commands

1.  **Set up prompttest:** `prompttest init`

2.  **Run your tests:** `prompttest`

## Folder Structure

`prompttest` works by looking for files in 2 specific folders:

-   `prompts/`: Your prompts live here as `.txt` files.

-   `prompttests/`: Your tests and configs live here as `.yml` files.

## Anatomy of a Test

`prompttest` uses 3 types of key files.

### 1. Prompt File (`.txt`)

This is a simple text file containing your prompt.

It uses sections and variables.

-   `---[SYSTEM]---`: Defines the system prompt or initial instructions.

-   `---[USER]---`: Defines the user's message or input.

-   `{variable_name}`: Placeholders that will be filled in by your test cases.

**Example:**

`prompts/customer_service.txt`

```txt
---[SYSTEM]---
You are an expert on the "{product_name}".
Your responses must be helpful and polite.

---[USER]---
Customer tier: {user_tier}
Customer query: {user_query}
```

### 2. Test File (`.yml`)

This file runs a set of tests against a prompt.

-   **`config` block:** Settings for all tests in this file.

    -   `prompt`: The name of the prompt to test (without `.txt`).

    -   `generation_model` (optional): Use a specific model to write responses.

    -   `evaluation_model` (optional): Use a specific model to judge responses.

-   **`tests` block:** A list of your test cases. **Each test starts with a dash (`-`)** and needs the following keys:

    -   `id`: A unique name for the test.

    -   `inputs`: The values for the prompt's {variable_name} placeholders.

    -   `criteria`: Instructions for the AI judge.

**Example:**

`prompttests/test_customers.yml`

```yaml
config:
  # This will test the "customer_service.txt" prompt.
  prompt: customer_service

tests:
  - id: check-simple-greeting
    inputs:
      product_name: "Chrono-Watch"
      user_tier: "Standard"
      user_query: "Hello"
    criteria: "The response must be a simple, polite greeting."
```

### 3. Config File (`prompttest.yml`)

This file is the key to keeping your tests clean and organized.

It lets you define settings and reusable values that can be shared across all your tests.

-   **`config` block:** Defines the default settings for all tests.

    -   `generation_model`: The default model that writes the response.

    -   `evaluation_model`: The default model that judges the response.

-   **`reusable` block:** Define values you use often.

    -   `&`: Create a named reusable value or group.

    -   `>`: Write a long, multi-line string.

**Example:**

`prompttests/prompttest.yml`

```yaml
config:
  generation_model: "openai/gpt-oss-20b:free"
  evaluation_model: "mistralai/mistral-small-3.2-24b-instruct:free"

reusable:
  inputs:
    product_name: &product_name "Chrono-Watch"
    standard_user: &standard_user
      user_name: "Alex"
      user_tier: "Premium"
  criteria:
    is_polite: &is_polite >
      The response must be polite, friendly, and helpful. It should adopt
      an empathetic tone, especially if the user seems frustrated or angry.
```

You can then use these reusable values in any test file.

-   `*`: Use a reusable value.

-   `<<:`: Use a reusable group of values.

**Example:**

`prompttests/support.yml`

```yaml
config:
  prompt: customer_service

tests:
  - id: check-premium-support
    inputs:
      <<: *standard_user       # Loads the group of values (user_name and user_tier)
      product_name: *product_name # Loads the single value
      user_query: "My watch is slow."
    criteria: *is_polite        # Loads the multi-line criteria
```

## Advanced Usage: Filtering Tests

While `prompttest` runs all tests by default, you can use the `run` command to target specific tests.

-   **Run all tests in a folder:**
    ```bash
    prompttest run customer_service/
    ```

-   **Run all tests in a file:**
    ```bash
    prompttest run test_customers.yml
    ```

-   **Run a specific test by ID:**
    ```bash
    # You can use a full ID or a wildcard pattern
    prompttest run check-simple-greeting
    prompttest run "check-*"
    ```

## Organizing Larger Projects

For larger projects, you can organize your tests into subfolders inside `prompttests/`.

Each subfolder can have its own config file (`prompttest.yml`).

**Example Structure:**

```
prompttests/
├── prompttest.yml      # Global config for all tests
│
└── customer_service/
    ├── prompttest.yml  # Local config; its settings take priority for this folder.
    └── returns.yml     # Can use settings from BOTH config files.
```
