package glamor;

import org.jline.terminal.TerminalBuilder;
import java.io.IOException;

public class ProgressBar {

    private final long total;
    private long current = 0;

    public ProgressBar(long total) {
        this.total = total;
    }

    public synchronized void update(long value) {
        current = value;
        render();
    }

    private void render() {
        double pct = (double) current / total;
        int bars = (int) (pct * 30);

        String bar = "[" + "=".repeat(bars) + " ".repeat(30 - bars) + "]";
        System.out.printf("\r%s %d/%d (%.1f%%)", bar, current, total, pct * 100);
        System.out.flush();
    }
}

