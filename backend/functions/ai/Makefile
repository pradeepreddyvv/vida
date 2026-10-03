.PHONY: build-VidaAiFunction

build-VidaAiFunction:
	mkdir -p $(ARTIFACTS_DIR)/shared
	cp -r $(CURDIR)/shared/* $(ARTIFACTS_DIR)/shared/
	cp $(CURDIR)/shared/__init__.py $(ARTIFACTS_DIR)/shared/__init__.py
	cp $(CURDIR)/ai/handler.py $(ARTIFACTS_DIR)/handler.py
	pip install -r $(CURDIR)/ai/requirements.txt -t $(ARTIFACTS_DIR)/ --quiet
