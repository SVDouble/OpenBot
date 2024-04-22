# OpenBot

## Overview
OpenBot is an open-source framework designed to simplify the development of bots, initially for Telegram, with the capability to extend to other platforms. Utilizing a state machine model, it allows for defining complex behaviors in bots through various states and transitions.

## Key Features
- **State Machine Framework**: Leveraging YAML files with embedded Python code, OpenBot allows defining detailed bot behaviors through a robust state machine approach.
- **Cross-Platform Compatibility**: While primarily for Telegram, the framework is structured to support additional platforms such as Discord.
- **Dynamic Data Integration**: Bot interactions can pull data dynamically from APIs or be defined statically within the YAML configuration files.
- **Redis Integration**: Utilizes Redis for effective state management and data caching, ensuring quick access and responsiveness.
- **Hierarchical and Parallel States**: Supports advanced state management features like hierarchical and parallel states, enabled by the Sismic library.
- **Containerization**: Facilitates deployment using Docker, ensuring consistent environments across development and production.
- **Poetry for Dependency Management**: Uses Poetry, streamlining library management and package installations.
- **Multiple Bot Examples**: Includes a variety of example configurations in the `examples` folder to kickstart your bot development <i>(coming soon)</i>.

## Getting Started
To begin using OpenBot, clone the repository and navigate to the respective directory. Install dependencies using Poetry and deploy bots using Docker Compose.

## Contributing
Contributions are welcome at OpenBot, whether they are for bug fixes, new features, or documentation improvements.

## License
OpenBot is distributed under the MIT License, except for parts extending the Sismic library, which are bound by the LGPL-3.0 License.

## Contact
If you have any questions, suggestions, or need support with OpenBot, please open an issue in the GitHub repository.

---

Developed by Valentin Safronov | Since 2022
