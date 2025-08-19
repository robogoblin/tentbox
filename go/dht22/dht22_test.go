package dht22

import (
	"testing"
	"time"

	"github.com/morus12/dht22"
)

func TestDHTManager(t *testing.T) {
	s1 := NewDHT22(19, "top of tent", "tent")
	m := NewManager()
	m.AddSensor(s1)
	m.StartReadCycle(5 * time.Second)
	defer m.StopReadCycle()

	time.Sleep(20 * time.Second)
}

func TestMorusDht22(t *testing.T) {
	sensor := dht22.New("GPIO13")
	temperature, err := sensor.Temperature()
	if err != nil {
		t.Fatalf("Failed to read temperature: %v", err)
	}
	humidity, err := sensor.Humidity()
	if err != nil {
		t.Fatalf("Failed to read humidity: %v", err)
	}
	t.Logf("temperature: %v, humidity: %v", temperature, humidity)
}
