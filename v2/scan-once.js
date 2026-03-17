const { runScanner } = require('./signals/scanner');
const { scoreSignals } = require('./signals/scorer');

async function main() {
  try {
    console.log('=== RCT Trader Daily Scan ===');
    console.log(`Scan time: ${new Date().toISOString()}`);
    console.log('');
    
    const signals = await runScanner();
    const ranked = scoreSignals(signals);
    
    console.log(`Total signals found: ${signals.length}`);
    console.log('');
    
    if (ranked.length === 0) {
      console.log('No signals found.');
    } else {
      console.log('Top 10 signals:');
      ranked.slice(0, 10).forEach((signal, i) => {
        const source = signal.meta?.source || signal.source || 'unknown';
        console.log(`${i + 1}. ${signal.symbol} - ${signal.strategy} (score: ${signal.totalScore.toFixed(2)}) [source: ${source}]`);
      });
    }
    
    // Check if all signals are mock data
    const allMock = signals.length > 0 && signals.every(s => {
      const source = s.meta?.source || s.source;
      return source === 'mock';
    });
    if (allMock) {
      console.log('');
      console.log('⚠️  WARNING: All signals show source:mock - FMP_API_KEY may be missing or invalid');
    }
    
    console.log('');
    console.log('Scan complete.');
    process.exit(0);
  } catch (err) {
    console.error('Error during scan:', err.message);
    console.error(err.stack);
    process.exit(1);
  }
}

main();
