package main

import (
	"flag"
	"fmt"

	"github.com/GreediGoblins/tentbox/go/config"
)

func main() {
	showConfigExample := flag.Bool("show-config-example", false, "Show example config")
	flag.Parse()

	if *showConfigExample {
		fmt.Println(config.ExampleConfig())
	}
}
