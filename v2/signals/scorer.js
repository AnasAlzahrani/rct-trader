function scoreSignals(signals) {
  return signals
    .map((signal) => {
      const weight =
        signal.strategy === 'PEAD'
          ? 1
          : signal.strategy === 'INSIDER_CLUSTER'
            ? 0.9
            : 0.7;
      return { ...signal, totalScore: signal.score * weight };
    })
    .sort((a, b) => b.totalScore - a.totalScore);
}

module.exports = { scoreSignals };
