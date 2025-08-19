package config

import (
	"encoding/json"
	"fmt"
)

var example_config = &Config{
	WebServer: &WebServer{
		HttpPort:    8080,
		HttpAddress: "0.0.0.0",
	},
	Dht22: []*Dht22Config{
		{
			Pin:      4,
			Name:     "Living Room",
			Location: "Home",
		},
	},
	DS18B20: []*DS18B20{
		{
			Id:       "28-000005e2a3c1",
			Name:     "Bedroom",
			Location: "Home",
		},
	},
	Relay: []*Relay{
		{
			Name:     "Light",
			Location: "Living Room",
			Default:  true,
		},
	},
}

func ExampleConfig() string {
	out, err := json.MarshalIndent(example_config, "", "  ")
	if err != nil {
		panic(fmt.Errorf("failed to marshal example config: %w", err))
	}
	return string(out)
}
