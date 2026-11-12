import ch.qos.logback.classic.Level;
import ch.qos.logback.classic.LoggerContext;
import ch.qos.logback.classic.encoder.PatternLayoutEncoder;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.classic.util.LogbackMDCAdapter;
import ch.qos.logback.core.rolling.RollingFileAppender;
import ch.qos.logback.core.rolling.SizeAndTimeBasedRollingPolicy;
import ch.qos.logback.core.util.FileSize;

import java.nio.file.Files;
import java.nio.file.Path;

/** Writes only synthetic JSON into a disposable test volume using real Logback. */
public class LogRotationWriter {
    private static final int ROLLOVER_CHECK_DELAY_MS = 120;

    public static void main(String[] arguments) throws Exception {
        Path input = Path.of(arguments[0]);
        String directory = arguments[1];
        LoggerContext context = new LoggerContext();
        context.setMDCAdapter(new LogbackMDCAdapter());
        context.start();
        PatternLayoutEncoder encoder = new PatternLayoutEncoder();
        encoder.setContext(context);
        encoder.setPattern("%msg%n");
        encoder.start();

        RollingFileAppender<ILoggingEvent> appender = new RollingFileAppender<>();
        appender.setContext(context);
        appender.setEncoder(encoder);

        SizeAndTimeBasedRollingPolicy<ILoggingEvent> policy =
                new SizeAndTimeBasedRollingPolicy<>();
        policy.setContext(context);
        policy.setParent(appender);
        policy.setFileNamePattern(directory + "/spool/app.%d{yyyy-MM-dd}.%i.log");
        policy.setMaxFileSize(FileSize.valueOf("4KB"));
        policy.setMaxHistory(2);
        policy.setTotalSizeCap(FileSize.valueOf("128KB"));
        policy.start();

        appender.setRollingPolicy(policy);
        appender.setTriggeringPolicy(policy);
        appender.start();
        if (!appender.isStarted()) {
            throw new IllegalStateException("Fixture rolling appender did not start");
        }

        var logger = context.getLogger("rotation-fixture");
        logger.setLevel(Level.INFO);
        logger.setAdditive(false);
        logger.addAppender(appender);

        try {
            for (String line : Files.readAllLines(input)) {
                logger.info(line);
                Thread.sleep(ROLLOVER_CHECK_DELAY_MS);
            }
        } finally {
            appender.stop();
            context.stop();
        }
    }
}
