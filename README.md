# ETH Debate

A small static website for mapping debate topics.


## Local setup

Setup a virtual environment:
```bash
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

Build the site:
```bash
python3 build.py && python3 -m http.server 8000 --directory public
```


## Adding new topics

1. Copy `content/issuance/` and rename, such as `content/focil/`.
2. Update `content/focil/topic.yaml`. Keep `slug`, and add any topic-specific overrides such as `title`, `description`, `eyebrow`, `hero_title`, or `social_image` if they should differ from `config.yaml`.
3. Update the content files:
   - `topic.yaml`
   - `overview.md`
   - `potential-paths.yaml`
   - `key-resources.yaml`
   - `arguments-for.yaml`
   - `arguments-against.yaml`
4. Add source files to the topics source folder, such as `content/issuance/sources`


## Netlify

The included `netlify.toml` handles the build and homepage redirect.

Netlify settings:

```text
Build command: python3 -m pip install -r requirements.txt && python3 build.py
Publish directory: public
```
