# 🔵 [WIP] F2: Support AGENTS_BUNDLE_VARS environment variable for personal default key=val overrides

- Parse key=val pairs from AGENTS_BUNDLE_VARS in the environment as user-level defaults (overridable by CLI key=val arguments) so personal settings such as chat_lang=<lang> do not need to be committed into repository .agents_bundle files.
