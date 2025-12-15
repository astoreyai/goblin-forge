package logging

import (
	"io"
	"os"
	"time"

	"github.com/rs/zerolog"
)

// Logger wraps zerolog for structured logging
type Logger struct {
	zl zerolog.Logger
}

// New creates a new logger instance
func New(verbose bool) *Logger {
	// Configure output format
	output := zerolog.ConsoleWriter{
		Out:        os.Stderr,
		TimeFormat: time.RFC3339,
		NoColor:    false,
	}

	// Set log level
	level := zerolog.InfoLevel
	if verbose {
		level = zerolog.DebugLevel
	}

	zl := zerolog.New(output).
		Level(level).
		With().
		Timestamp().
		Logger()

	return &Logger{zl: zl}
}

// NewWithWriter creates a logger with a custom writer
func NewWithWriter(w io.Writer, verbose bool) *Logger {
	level := zerolog.InfoLevel
	if verbose {
		level = zerolog.DebugLevel
	}

	zl := zerolog.New(w).
		Level(level).
		With().
		Timestamp().
		Logger()

	return &Logger{zl: zl}
}

// Debug logs a debug message
func (l *Logger) Debug(msg string, fields ...Field) {
	event := l.zl.Debug()
	for _, f := range fields {
		event = f.apply(event)
	}
	event.Msg(msg)
}

// Info logs an info message
func (l *Logger) Info(msg string, fields ...Field) {
	event := l.zl.Info()
	for _, f := range fields {
		event = f.apply(event)
	}
	event.Msg(msg)
}

// Warn logs a warning message
func (l *Logger) Warn(msg string, fields ...Field) {
	event := l.zl.Warn()
	for _, f := range fields {
		event = f.apply(event)
	}
	event.Msg(msg)
}

// Error logs an error message
func (l *Logger) Error(msg string, err error, fields ...Field) {
	event := l.zl.Error()
	if err != nil {
		event = event.Err(err)
	}
	for _, f := range fields {
		event = f.apply(event)
	}
	event.Msg(msg)
}

// Fatal logs a fatal message and exits
func (l *Logger) Fatal(msg string, err error, fields ...Field) {
	event := l.zl.Fatal()
	if err != nil {
		event = event.Err(err)
	}
	for _, f := range fields {
		event = f.apply(event)
	}
	event.Msg(msg)
}

// Field represents a log field
type Field struct {
	key   string
	value interface{}
}

// apply adds the field to a zerolog event
func (f Field) apply(event *zerolog.Event) *zerolog.Event {
	switch v := f.value.(type) {
	case string:
		return event.Str(f.key, v)
	case int:
		return event.Int(f.key, v)
	case int64:
		return event.Int64(f.key, v)
	case float64:
		return event.Float64(f.key, v)
	case bool:
		return event.Bool(f.key, v)
	case error:
		return event.AnErr(f.key, v)
	case time.Duration:
		return event.Dur(f.key, v)
	case time.Time:
		return event.Time(f.key, v)
	default:
		return event.Interface(f.key, v)
	}
}

// String creates a string field
func String(key, value string) Field {
	return Field{key: key, value: value}
}

// Int creates an int field
func Int(key string, value int) Field {
	return Field{key: key, value: value}
}

// Int64 creates an int64 field
func Int64(key string, value int64) Field {
	return Field{key: key, value: value}
}

// Float64 creates a float64 field
func Float64(key string, value float64) Field {
	return Field{key: key, value: value}
}

// Bool creates a bool field
func Bool(key string, value bool) Field {
	return Field{key: key, value: value}
}

// Err creates an error field
func Err(err error) Field {
	return Field{key: "error", value: err}
}

// Duration creates a duration field
func Duration(key string, value time.Duration) Field {
	return Field{key: key, value: value}
}

// Time creates a time field
func Time(key string, value time.Time) Field {
	return Field{key: key, value: value}
}

// Any creates a field with any value
func Any(key string, value interface{}) Field {
	return Field{key: key, value: value}
}
