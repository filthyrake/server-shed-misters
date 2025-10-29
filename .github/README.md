# GitHub Copilot Configuration

This directory contains configuration files for GitHub Copilot coding agent to help it understand and work with this repository effectively.

## Files

### `copilot-instructions.md`
Main instructions file that provides Copilot with:
- Project overview and context
- Development workflow and commands
- Architecture and design patterns
- Critical implementation details
- Safety guidelines for hardware control
- Testing and deployment procedures

This file is automatically loaded by Copilot when working on issues in this repository.

### `agents/` Directory
Contains custom agent profiles for specialized tasks:

#### `hardware-safety-agent.md`
Specialized agent for ensuring safety when modifying code that controls physical hardware (water valves and sensors). Use this agent when:
- Modifying misting decision logic
- Changing state management
- Updating emergency stop or cooldown mechanisms
- Reviewing changes that affect valve control

#### `api-integration-agent.md`
Specialized agent for working with SwitchBot and Rachio APIs. Use this agent when:
- Adding or modifying API endpoints
- Changing authentication patterns
- Updating device discovery logic
- Handling temperature conversion (Celsius ↔ Fahrenheit)
- Troubleshooting API connectivity issues

#### `docker-deployment-agent.md`
Specialized agent for Docker configuration and deployment. Use this agent when:
- Modifying Docker Compose files
- Updating Dockerfile
- Changing deployment scripts
- Configuring systemd service
- Setting up production environments
- Troubleshooting deployment issues

## Usage

### For GitHub Copilot Coding Agent
When you assign an issue to Copilot:
1. Copilot automatically loads `copilot-instructions.md`
2. For specialized tasks, mention the appropriate agent in the issue description
3. Agents provide focused expertise for their specific domains

### For Custom Agents
Custom agents are automatically available to Copilot when working on issues. They provide specialized expertise based on the task context. Copilot will select the appropriate agent based on:
- The issue description and labels
- The files being modified
- The type of changes requested

To help Copilot choose the right agent, include relevant keywords in your issue description:
- For hardware safety: "valve control", "misting logic", "safety review"
- For API changes: "SwitchBot API", "Rachio integration", "device discovery"
- For deployment: "Docker", "deployment", "production configuration"

## Best Practices

1. **Keep Instructions Updated**: When making significant architectural changes, update `copilot-instructions.md`
2. **Use Specialized Agents**: Leverage custom agents for domain-specific tasks
3. **Safety First**: Always use `hardware-safety-agent` for changes affecting physical hardware control
4. **Clear Issues**: Write detailed issue descriptions to help Copilot understand context
5. **Review Changes**: Always review Copilot's PRs before merging, especially for safety-critical code

## References

For more information about GitHub Copilot coding agent and custom agents:
- [GitHub Copilot Coding Agent Documentation](https://docs.github.com/en/copilot)
- [GitHub Copilot Best Practices Blog](https://github.blog/tag/copilot/)

Note: GitHub documentation and features may evolve. Check the official GitHub docs for the latest information.
