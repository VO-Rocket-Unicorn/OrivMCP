package odas

import (
	"fmt"
	"runtime/debug"
)

// recovering returns fn with any panic turned into its error.
//
// It wraps work a request fans out to its own goroutines: a panic there is
// past the reach of the MCP middleware's recover, so unwrapped it would end
// the process.
func recovering(fn func() error) func() error {
	return func() (err error) {
		defer func() {
			if r := recover(); r != nil {
				err = fmt.Errorf("panic in ODAS request: %v\n%s", r, debug.Stack())
			}
		}()
		return fn()
	}
}
