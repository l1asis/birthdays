<!-- omit in toc -->
# Contributing to birthdays

First off, thanks for taking the time to contribute! ❤️

All types of contributions are encouraged and valued. See the [Table of Contents](#table-of-contents) for different ways to help and details about how this project handles them. Please make sure to read the relevant section before making your contribution. It will make it a lot easier for me as the maintainer and smooth out the experience for everyone involved. I look forward to your contributions! 🎉

> [!NOTE]
> If you like the project, but just don't have time to contribute, that's fine. There are other easy ways to support the project and show your appreciation, which I would also be very happy about:
>
> - Star the project
> - Share it on social media
> - Refer this project in your project's readme
> - Mention the project at local meetups and tell your friends/colleagues

> [!IMPORTANT]
> **A quick note on "I" vs. "We":**
> I write as "I" because I'm currently the only maintainer, but I'm always open to collaboration. If you become an active contributor or co-maintainer, "I" happily becomes "We"!

<!-- omit in toc -->
## Table of Contents

- [I Have a Question](#i-have-a-question)
- [I Want To Contribute](#i-want-to-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Enhancements](#suggesting-enhancements)
  - [Your First Code Contribution](#your-first-code-contribution)
  - [Improving The Documentation](#improving-the-documentation)
- [Styleguides](#styleguides)
  - [Versioning](#versioning)
  - [Commit Messages](#commit-messages)
  - [Formatting](#formatting)

## I Have a Question

Before you ask a question, it is best to search for existing [Issues](https://github.com/l1asis/birthdays/issues) that might help you. In case you have found a suitable issue and still need clarification, you can write your question in this issue. It is also advisable to search the internet for answers first.

If you then still feel the need to ask a question and need clarification, I recommend the following:

- Open an [Issue](https://github.com/l1asis/birthdays/issues/new).
- Add the `question` tag.
- Provide as much context as you can about what you're running into.
- Provide **project** and **platform** versions (Python, OS, etc.), depending on what seems relevant.

I will then take care of the issue as soon as possible.

## I Want To Contribute

<!-- omit in toc -->
### Legal Notice

When contributing to this project, you must agree that you have authored 100% of the content, that you have the necessary rights to the content, and that the content you contribute may be provided under the project license.

<!-- omit in toc -->
### AI Usage Policy

Purely AI-generated or autonomous agent submissions will be closed without review. All contributions should be manually written (mistake-checks are fine, though) and understood by the contributor.

The main question: **Why?**

When I started programming, there were no LLMs ready to cover all of the tasks one could only dream of. I remember having fun and pain learning things, drilling through documentation trying to find the needed function, and reading Stack Overflow in order to find the solution to a non-trivial problem. Today it is different, and it is very tempting to prompt-engineer everything from A to B, only reviewing the code made by the AI, but I believe it is not the right way. I made the mistake myself and kept committing and committing without noticing how dependent I became on this technology and how much lazier I was getting about writing something myself, despite the fact that I was always trying to understand *why* and *how* and put a lot of effort into the review process. It might be my personal problem or incompetence, but I see a danger in over-relying on it and want to change. While saying this, I find that it is completely fine to use it to learn things, it is legit to check your work, and it is completely normal to try to brainstorm ideas with it or get inspiration / build boilerplate based on your idea.

This view collides with the vibe-coding practice we see everywhere being heavily applied now.

If you don't share this opinion, I understand you.
If you are masking your contribution by making it as close to human-written as possible, I probably wouldn't be able to notice.

But then again, you've still applied some human power to do so anyway :blush:

### Reporting Bugs

<!-- omit in toc -->
#### Before Submitting a Bug Report

A good bug report shouldn't leave me needing to chase you up for more information. Therefore, I ask you to investigate carefully, collect information, and describe the issue in detail in your report. Please complete the following steps in advance to help me fix any potential bug as fast as possible.

1. Make sure that you are using the latest version.
2. Determine if your bug is really a bug and not an error on your side, e.g., using incompatible environment components/versions.
3. To see if other users have experienced (and potentially already solved) the same issue you are having, check if there is not already a bug report existing for your bug or error in the [bug tracker](https://github.com/l1asis/birthdays/issues?q=label%3At%3Abug).
4. Also make sure to search the internet (including Stack Overflow) to see if users outside of the GitHub community have discussed the issue.
5. Collect information about the bug:
   - Stack trace (Traceback)
   - OS, Platform, and Version (Windows, Linux, macOS, x86, ARM)
   - Version of the interpreter, compiler, SDK, runtime environment, or package manager, depending on what seems relevant
   - Possibly your input and the output
   - Can you reliably reproduce the issue? And can you also reproduce it with older versions?

<!-- omit in toc -->
#### How Do I Submit a Good Bug Report?

> [!WARNING]
>
> You must never report security-related issues, vulnerabilities, or bugs including sensitive information to the issue tracker, or elsewhere in public. Instead, sensitive bugs must be sent through [GitHub's private vulnerability reporting](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/report-privately).

I use GitHub issues to track bugs and errors. If you run into an issue with the project:

- Open an [Issue](https://github.com/l1asis/birthdays/issues/new).
- Explain the behavior you would expect and the actual behavior.
- Please provide as much context as possible and describe the *reproduction steps* that someone else can follow to recreate the issue on their own. This usually includes your code. For good bug reports, you should isolate the problem and create a reduced test case.
- Provide the information you collected in the previous section.

Once it's filed:

- I will label the issue accordingly.
- I will try to reproduce the issue with your provided steps.
- If I am able to reproduce the issue, it will be marked with a certain tag, and the issue will be left to be [implemented by someone](#your-first-code-contribution) (or fixed by me).

### Suggesting Enhancements

This section guides you through submitting an enhancement suggestion for `birthdays`, **including completely new features and minor improvements to existing functionality**. Following these guidelines will help me and the community understand your suggestion and find related suggestions.

<!-- omit in toc -->
#### Before Submitting an Enhancement

- Make sure that you are using the latest version.
- Perform a [search](https://github.com/l1asis/birthdays/issues) to see if the enhancement has already been suggested. If it has, add a comment to the existing issue instead of opening a new one.
- Find out whether your idea fits with the scope and aims of the project. It's up to you to make a strong case to convince me of the merits of this feature.

<!-- omit in toc -->
#### How Do I Submit a Good Enhancement Suggestion?

Enhancement suggestions are tracked as [GitHub issues](https://github.com/l1asis/birthdays/issues).

- Use a **clear and descriptive title** for the issue to identify the suggestion.
- Provide a **step-by-step description of the suggested enhancement** in as many details as possible.
- **Describe the current behavior** and **explain which behavior you expected to see instead** and why. At this point, you can also tell which alternatives do not work for you.
- You may want to **include screenshots or terminal output** to help demonstrate the steps or point out the part that the suggestion is related to.
- **Explain why this enhancement would be useful** to most `birthdays` users. You may also want to point out other projects that solved it better and which could serve as inspiration.

### Your First Code Contribution

You can use any editor you feel comfortable with to contribute. Some popular options include Visual Studio Code, PyCharm, Spyder, Python IDLE, etc.

Make sure you have the latest Python version supported by the project installed. Then, the typical steps look like this:

1. Clarify or discuss your goal or work item
2. Fork the project or make sure your existing fork is up-to-date
3. Clone your fork to have it locally
4. Create a virtual environment (e.g., using `venv` or `uv`)
5. Install the dependencies (e.g., using `pip` or `uv`), if applicable
6. Create an appropriate branch (e.g., `git checkout -b feat/amazing-feature`)
7. Make your changes
8. Test your changes and make sure they are not breaking anything
9. Make sure to format your code as described in the sections below
10. Commit your changes (e.g., `git commit -m 'feat: ✨ add some amazing feature'`)
11. Push to the branch (`git push origin feat/amazing-feature`)
12. Open a pull request

Please note that your workflow might be different and this is just an example.

### Improving The Documentation

Documentation changes (e.g., changes in the `README.md`) should be concise, sharp, and accurate. They could reflect some added features or be something that you would personally benefit from seeing when visiting the repository for the first time.

Feel free to correct mistakes if there are any!

## Styleguides

### Versioning

I use the [Semantic Versioning](https://semver.org/) system for this project.

### Commit Messages

All commits should follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification.

<!-- omit in toc -->
#### Short overview

The format is the following:

```plaintext
<type>([optional scope]): [optional emoji] <description>

[optional body]

[optional footer(s)]
```

It is common practice to use the following types:

```plaintext
feat: ✨ add some amazing feature
fix: 🐛 resolve some bug
docs: 📝 update some documentation
style: 🎨 fix formatting and code style
refactor: ♻️ clean up some code logic
perf: ⚡ improve performance of some logic
test: ✅ add some missing tests
build: 📦 update some dependencies
ci: 👷 modify some configuration
chore: 🔧 do some maintenance task
revert: ⏪ roll back some previous commit
```

### Formatting

I use the [`ruff`](https://github.com/astral-sh/ruff) formatting tool made by Astral. It is quick, powerful, and makes the code look unified.

Always format your code using the following command:

```bash
ruff format .
```

Always use the following to check for deviations from the style rules:

```bash
ruff check . --fix
```

Both commands assume you're in the root project directory (thus with a dot).

## Attribution

This guide is based on the [contributing.md](https://contributing.md/generator) generator!
