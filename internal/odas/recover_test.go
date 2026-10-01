package odas

import (
	"errors"
	"strings"
	"testing"
)

func TestRecoveringTurnsAPanicIntoAnError(t *testing.T) {
	err := recovering(func() error { panic("boom") })()
	if err == nil || !strings.Contains(err.Error(), "panic in ODAS request: boom") {
		t.Errorf("err = %v", err)
	}
}

func TestRecoveringPassesErrorsThrough(t *testing.T) {
	want := errors.New("plain")
	if err := recovering(func() error { return want })(); err != want {
		t.Errorf("err = %v", err)
	}
}
