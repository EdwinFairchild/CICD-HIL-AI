#ifndef LED_H
#define LED_H

#include "main.h"
#include "gpio.h"
#include "stdint.h"
#include "stm32h723xx.h"




typedef struct {
    Led_TypeDef id;
    uint32_t delay_ms;
    uint32_t lastBliknk;
}led_t;


void led_init(led_t *led, Led_TypeDef id, uint32_t delay_ms);
void led_set_delay(led_t *led, uint32_t delay_ms);
void led_updates(led_t leds[], uint8_t num_leds);


#endif // LED_H