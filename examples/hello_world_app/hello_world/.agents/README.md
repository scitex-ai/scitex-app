# Agents in this app

`scitex-app app validate` requires `.agents/agents.json` or `.agents/README.md`
beside a standalone app. This app declares NO agents, and this file says so
explicitly rather than leaving the question unanswered.

The distinction matters and is the reason the check accepts a README as well as
a JSON file: an app with no agents and an app whose agent declaration was
forgotten are indistinguishable from an empty directory. One is a decision, the
other is an omission, and only the first should pass.

If you add agents, replace this with `agents.json`:

    {
      "agents": [
        {
          "name": "greeter",
          "description": "What it does, in one line.",
          "entrypoint": "hello_world.agents:greeter"
        }
      ]
    }
