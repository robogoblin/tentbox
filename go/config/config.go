package config

type Config struct {
	WebServer *WebServer     `json:"webserver"`
	Dht22     []*Dht22Config `json:"dht22"`
	DS18B20   []*DS18B20     `json:"ds18b20"`
	Relay     []*Relay       `json:"relay"`
}

type WebServer struct {
	HttpPort    int    `json:"http_port"`
	HttpAddress string `json:"http_address"`
}

type Dht22Config struct {
	Pin      int    `json:"pin"`
	Name     string `json:"name"`
	Location string `json:"location"`
}

type DS18B20 struct {
	Id       string `json:"id"`
	Name     string `json:"name"`
	Location string `json:"location"`
}

type Relay struct {
	Name     string `json:"name"`
	Location string `json:"location"`
	Default  bool   `json:"default"`
}
