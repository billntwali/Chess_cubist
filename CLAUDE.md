
You're the participant at a quant dev hackathon, and this year's topic is "Build your own chess engine from scratch or on top of existing foundations." Have an ideation phase, development phase, and testing phase. Ask me questions for any clarifications.

Below are details of the hackathon. 

There are four judging criteria: creativity, rigor, ingenuity, and engineering. The details are below:

1. Chess Engine Quality
	- Does it play legal, strategic chess?
	- Correctness matters, but perfection is not the bar

2. AI Usage
	- How did your team use Claude?
	- Did you critically evaluate and iteration on AI-generate code?
	- Did you run experiments – e.g. pitting two AI generated engines against each other?
	- Did you think about cost and efficiency – getting more out of each prompt, using local/free models where appropriate?

3. Process and parallelization
	- Did you divide work intelligently across team members and AI accounts?
	- Evidence of parallel workstreams, code review, integration

4. Engineering quality: 
	- Documentation (README, docstrings, comments)
	- testing(unit tests, perft tests, self-play benchmarks)
	- research of prior art(existing engines, papers, the UCI protocol)

Chess Interfaces and protocols:
- Universal Chess Interface (UCI)
- python-chess: python-chess.readthedocs.io
- stockfish (reference engine): stockfishchess.org
- github.com/lichess-org

Additional Information:
- You may use any language or framework
- Evidence of process (research, experiments, documentation, testing) is important
- What language to use is up to us: Python, Rust, C++, Typescript, etc
- Existing chess libraries are allowed and encouraged as foundations
