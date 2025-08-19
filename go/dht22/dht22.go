package dht22

import (
	"encoding/json"
	"fmt"
	"sync"
	"time"

	dht "github.com/d2r2/go-dht"
)

type DHT22 struct {
	sync.RWMutex
	pin      int
	Name     string  `json:"name"`
	Location string  `json:"location"`
	Temp     float64 `json:"temp"`
	Humidity float64 `json:"humidity"`
}

func NewDHT22(pin int, name string, location string) *DHT22 {
	return &DHT22{
		pin:      pin,
		Name:     name,
		Location: location,
	}
}

func (d *DHT22) SetName(name string) {
	d.Lock()
	defer d.Unlock()
	d.Name = name
}

func (d *DHT22) SetLocation(location string) {
	d.Lock()
	defer d.Unlock()
	d.Location = location
}

func (d *DHT22) read() {
	temperature, humidity, retried, err := dht.ReadDHTxxWithRetry(dht.DHT22, d.pin, false, 3)
	if err != nil {
		fmt.Printf("Failed to get a successful reading after %d attempts\n", retried)
		return
	}
	d.Temp = float64(temperature)
	d.Humidity = float64(humidity)
}

type Manager struct {
	Sensors     map[int]*DHT22 `json:"dht22"`
	stopReading chan struct{}
}

func NewManager() *Manager {
	return &Manager{
		Sensors: make(map[int]*DHT22),
	}
}

func (dm *Manager) AddSensor(dht *DHT22) {
	dm.Sensors[dht.pin] = dht
}

func (dm *Manager) StartReadCycle(interval time.Duration) {
	dm.stopReading = make(chan struct{})
	go func() {
		ticker := time.NewTicker(interval)
		select {
		case <-dm.stopReading:
			ticker.Stop()
			return
		case <-ticker.C:
			for {
				for _, sensor := range dm.Sensors {
					sensor.read()
				}
				time.Sleep(interval)
			}
		}
	}()
}

func (dm *Manager) StopReadCycle() {
	close(dm.stopReading)
}

func (dm *Manager) String() string {
	data, _ := json.Marshal(dm)
	return string(data)
}
